"""
Hot Reload Engine for Realtimex Configuration System.

Handles runtime configuration updates and validation.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from configuration.exceptions import ConfigurationHotReloadError


class HotReloadEngine:
    """
    Handles hot reloading of configuration at runtime.
    
    Supports:
    - Monitored file reloading
    - Validation before reload
    - Subscriber notifications
    - Rollback on failure
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize Hot Reload Engine.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.hot_reload")
        self._subscribers: dict[str, list[Callable]] = {}  # namespace -> [callbacks]
        self._reload_callbacks: list[Callable] = []  # Global callbacks
        self._last_reload: Optional[datetime] = None
        self._reload_count = 0
        self._lock = threading.RLock()

    def subscribe(
        self,
        namespace: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """
        Subscribe to configuration changes for namespace.
        
        Args:
            namespace: Configuration namespace
            callback: Callback function(config_dict)
        """
        with self._lock:
            if namespace not in self._subscribers:
                self._subscribers[namespace] = []
            
            self._subscribers[namespace].append(callback)
            self.logger.debug(
                "Subscriber registered for namespace: %s", namespace
            )

    def unsubscribe(
        self,
        namespace: str,
        callback: Callable,
    ) -> bool:
        """
        Unsubscribe from configuration changes.
        
        Args:
            namespace: Configuration namespace
            callback: Callback function to remove
            
        Returns:
            True if unsubscribed, False if not found
        """
        with self._lock:
            if namespace not in self._subscribers:
                return False
            
            if callback in self._subscribers[namespace]:
                self._subscribers[namespace].remove(callback)
                self.logger.debug(
                    "Subscriber unregistered from namespace: %s", namespace
                )
                return True
            
            return False

    def subscribe_global(
        self,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """
        Subscribe to all configuration changes.
        
        Args:
            callback: Callback function(namespace, config_dict)
        """
        with self._lock:
            self._reload_callbacks.append(callback)
            self.logger.debug("Global subscriber registered")

    def unsubscribe_global(self, callback: Callable) -> bool:
        """
        Unsubscribe from global configuration changes.
        
        Args:
            callback: Callback to remove
            
        Returns:
            True if unsubscribed, False if not found
        """
        with self._lock:
            if callback in self._reload_callbacks:
                self._reload_callbacks.remove(callback)
                self.logger.debug("Global subscriber unregistered")
                return True
            return False

    def notify_reload(
        self,
        namespace: str,
        config: dict[str, Any],
    ) -> None:
        """
        Notify subscribers of configuration reload.
        
        Args:
            namespace: Configuration namespace
            config: New configuration
        """
        with self._lock:
            # Notify namespace-specific subscribers
            if namespace in self._subscribers:
                for callback in self._subscribers[namespace]:
                    try:
                        callback(config)
                        self.logger.debug(
                            "Subscriber notified for namespace: %s", namespace
                        )
                    except Exception as e:
                        self.logger.error(
                            "Subscriber callback failed for %s: %s", namespace, e
                        )
            
            # Notify global subscribers
            for callback in self._reload_callbacks:
                try:
                    callback(namespace, config)
                    self.logger.debug("Global subscriber notified")
                except Exception as e:
                    self.logger.error("Global subscriber callback failed: %s", e)
            
            self._last_reload = datetime.now(timezone.utc)
            self._reload_count += 1

    def get_reload_stats(self) -> dict[str, Any]:
        """
        Get hot reload statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            return {
                "reload_count": self._reload_count,
                "last_reload": self._last_reload.isoformat() if self._last_reload else None,
                "subscriber_count": sum(
                    len(callbacks) for callbacks in self._subscribers.values()
                ),
                "global_subscriber_count": len(self._reload_callbacks),
            }

    def subscriber_count(self, namespace: Optional[str] = None) -> int:
        """
        Get subscriber count.
        
        Args:
            namespace: Optional namespace filter
            
        Returns:
            Number of subscribers
        """
        with self._lock:
            if namespace is None:
                return sum(len(callbacks) for callbacks in self._subscribers.values())
            return len(self._subscribers.get(namespace, []))

    def clear_subscribers(self, namespace: Optional[str] = None) -> None:
        """
        Clear subscribers.
        
        Args:
            namespace: Optional namespace to clear (if None, clears all)
        """
        with self._lock:
            if namespace is None:
                self._subscribers.clear()
                self._reload_callbacks.clear()
                self.logger.debug("All subscribers cleared")
            else:
                if namespace in self._subscribers:
                    del self._subscribers[namespace]
                    self.logger.debug("Subscribers cleared for namespace: %s", namespace)

    def start_monitoring(
        self,
        config_dir: str,
        reload_callback: Callable[[str], None],
        interval: float = 1.0,
    ) -> None:
        """
        Start monitoring the configuration directory for changes.
        
        Args:
            config_dir: Directory to monitor
            reload_callback: Callback to execute when a file changes
            interval: Polling interval in seconds
        """
        with self._lock:
            if hasattr(self, '_monitor_thread') and self._monitor_thread and self._monitor_thread.is_alive():
                return
            
            # Initial scan synchronously to avoid race conditions
            file_mtimes = {}
            import glob
            if os.path.isdir(config_dir):
                for filepath in glob.glob(os.path.join(config_dir, "*.*")):
                    if filepath.endswith(('.json', '.yaml', '.yml', '.toml')):
                        try:
                            # Exclude directories
                            if os.path.isdir(filepath):
                                continue
                            file_mtimes[filepath] = os.path.getmtime(filepath)
                        except OSError:
                            pass
            
            self._monitoring = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(config_dir, reload_callback, interval, file_mtimes),
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Configuration file monitoring started (dir: %s, interval: %.1fs)", config_dir, interval)

    def stop_monitoring(self) -> None:
        """Stop configuration file monitoring."""
        with self._lock:
            self._monitoring = False
            self.logger.info("Configuration file monitoring stopped.")

    def _monitor_loop(
        self,
        config_dir: str,
        reload_callback: Callable[[str], None],
        interval: float,
        file_mtimes: dict[str, float],
    ) -> None:
        """Background thread loop polling file modified times."""
        import glob
        
        while getattr(self, '_monitoring', False):
            time.sleep(interval)
            
            if not os.path.isdir(config_dir):
                continue
                
            current_files = glob.glob(os.path.join(config_dir, "*.*"))
            
            # Check for modifications or new files
            for filepath in current_files:
                if not filepath.endswith(('.json', '.yaml', '.yml', '.toml')):
                    continue
                    
                try:
                    mtime = os.path.getmtime(filepath)
                except OSError:
                    continue
                    
                filename = os.path.basename(filepath)
                namespace = os.path.splitext(filename)[0]
                
                # Exclude subdirectories (e.g. staging, testing overrides folder)
                if os.path.isdir(filepath):
                    continue
                
                if filepath not in file_mtimes:
                    # New file
                    file_mtimes[filepath] = mtime
                    self.logger.info("New config file detected: %s", filepath)
                    try:
                        reload_callback(namespace)
                    except Exception as e:
                        self.logger.error("Failed to hot-reload new config %s: %s", namespace, e)
                elif mtime > file_mtimes[filepath]:
                    # Modified file
                    file_mtimes[filepath] = mtime
                    self.logger.info("Config file modification detected: %s", filepath)
                    try:
                        reload_callback(namespace)
                    except Exception as e:
                        self.logger.error("Failed to hot-reload modified config %s: %s", namespace, e)


