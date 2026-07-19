"""
Profile Manager for Realtimex Configuration System.

Manages multiple configuration profiles with precedence.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from configuration.exceptions import ProfileNotFoundError


class ProfileManager:
    """
    Manages configuration profiles.
    
    Supports multiple profiles:
    - Development: Verbose logging, debugging enabled
    - Testing: Mock services, minimal output
    - Production: Optimized settings, security hardened
    - Portable: Reduced resource usage
    - Offline: Standalone operation
    - Experimental: New/beta features enabled
    
    Profile precedence: Current profile > base profile > defaults
    """

    # Predefined profiles
    PROFILE_DEVELOPMENT = "development"
    PROFILE_TESTING = "testing"
    PROFILE_PRODUCTION = "production"
    PROFILE_PORTABLE = "portable"
    PROFILE_OFFLINE = "offline"
    PROFILE_EXPERIMENTAL = "experimental"

    PREDEFINED_PROFILES = {
        PROFILE_DEVELOPMENT,
        PROFILE_TESTING,
        PROFILE_PRODUCTION,
        PROFILE_PORTABLE,
        PROFILE_OFFLINE,
        PROFILE_EXPERIMENTAL,
    }

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """
        Initialize Profile Manager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.configuration.profiles")
        self._profiles: dict[str, dict[str, dict]] = {}  # name -> {namespace -> config}
        self._current_profile = self.PROFILE_DEVELOPMENT
        self._base_profile = self.PROFILE_DEVELOPMENT
        self._lock = threading.RLock()

    def create_profile(
        self,
        name: str,
        base_profile: Optional[str] = None,
        config: Optional[dict[str, dict]] = None,
    ) -> None:
        """
        Create a configuration profile.
        
        Args:
            name: Profile name
            base_profile: Optional base profile to inherit from
            config: Optional initial configuration
            
        Raises:
            ValueError: If profile already exists
        """
        with self._lock:
            if name in self._profiles:
                raise ValueError(f"Profile '{name}' already exists")
            
            if base_profile and base_profile not in self._profiles:
                if base_profile not in self.PREDEFINED_PROFILES:
                    raise ValueError(f"Base profile '{base_profile}' not found")
            
            # Start with base profile config
            if base_profile and base_profile in self._profiles:
                self._profiles[name] = {
                    namespace: cfg.copy()
                    for namespace, cfg in self._profiles[base_profile].items()
                }
            else:
                self._profiles[name] = {}
            
            # Apply custom config
            if config:
                for namespace, cfg in config.items():
                    if namespace in self._profiles[name]:
                        self._profiles[name][namespace].update(cfg)
                    else:
                        self._profiles[name][namespace] = cfg.copy()
            
            self.logger.info(
                "Profile created: %s (base=%s)", name,
                base_profile or "none"
            )

    def delete_profile(self, name: str) -> bool:
        """
        Delete a configuration profile.
        
        Args:
            name: Profile name
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if name not in self._profiles:
                return False
            
            if name == self._current_profile:
                raise ValueError(f"Cannot delete active profile '{name}'")
            
            del self._profiles[name]
            self.logger.info("Profile deleted: %s", name)
            return True

    def set_profile(self, name: str) -> None:
        """
        Set active configuration profile.
        
        Args:
            name: Profile name
            
        Raises:
            ProfileNotFoundError: If profile not found
        """
        with self._lock:
            if name not in self._profiles and name not in self.PREDEFINED_PROFILES:
                raise ProfileNotFoundError(f"Profile '{name}' not found")
            
            self._current_profile = name
            self.logger.info("Profile changed: %s", name)

    def get_profile(self) -> str:
        """
        Get active configuration profile.
        
        Returns:
            Current profile name
        """
        with self._lock:
            return self._current_profile

    def profile_exists(self, name: str) -> bool:
        """
        Check if profile exists.
        
        Args:
            name: Profile name
            
        Returns:
            True if profile exists
        """
        with self._lock:
            return name in self._profiles or name in self.PREDEFINED_PROFILES

    def set_profile_config(
        self,
        name: str,
        namespace: str,
        config: dict[str, Any],
        merge: bool = True,
    ) -> None:
        """
        Set configuration for a profile.
        
        Args:
            name: Profile name
            namespace: Configuration namespace
            config: Configuration dictionary
            merge: If True, merge with existing config
            
        Raises:
            ProfileNotFoundError: If profile not found
        """
        with self._lock:
            if name not in self._profiles:
                raise ProfileNotFoundError(f"Profile '{name}' not found")
            
            if merge and namespace in self._profiles[name]:
                self._profiles[name][namespace].update(config)
            else:
                self._profiles[name][namespace] = config.copy()
            
            self.logger.debug(
                "Profile configuration updated: %s.%s", name, namespace
            )

    def get_profile_config(
        self,
        name: str,
        namespace: Optional[str] = None,
    ) -> dict[str, dict] | dict:
        """
        Get profile configuration.
        
        Args:
            name: Profile name
            namespace: Optional specific namespace
            
        Returns:
            Configuration dictionary or namespace config
            
        Raises:
            ProfileNotFoundError: If profile not found
        """
        with self._lock:
            if name not in self._profiles:
                raise ProfileNotFoundError(f"Profile '{name}' not found")
            
            profile_config = self._profiles[name]
            
            if namespace is None:
                return {k: v.copy() for k, v in profile_config.items()}
            
            return profile_config.get(namespace, {}).copy()

    def list_profiles(self) -> list[str]:
        """
        List all available profiles.
        
        Returns:
            List of profile names
        """
        with self._lock:
            custom_profiles = list(self._profiles.keys())
            all_profiles = custom_profiles + list(self.PREDEFINED_PROFILES)
            return sorted(list(set(all_profiles)))

    def get_effective_config(
        self,
        namespace: str,
        defaults: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Get effective configuration for namespace.
        
        Merges: defaults < base_profile < current_profile
        
        Args:
            namespace: Configuration namespace
            defaults: Optional default values
            
        Returns:
            Effective configuration dictionary
        """
        with self._lock:
            config = {}
            
            # Start with defaults
            if defaults:
                config.update(defaults)
            
            # Apply base profile
            if self._base_profile in self._profiles:
                base_ns = self._profiles[self._base_profile].get(namespace, {})
                config.update(base_ns)
            
            # Apply current profile
            if self._current_profile in self._profiles:
                current_ns = self._profiles[self._current_profile].get(namespace, {})
                config.update(current_ns)
            
            return config

    def rename_profile(self, old_name: str, new_name: str) -> None:
        """
        Rename a profile.
        
        Args:
            old_name: Current profile name
            new_name: New profile name
            
        Raises:
            ProfileNotFoundError: If profile not found
            ValueError: If new name already exists
        """
        with self._lock:
            if old_name not in self._profiles:
                raise ProfileNotFoundError(f"Profile '{old_name}' not found")
            
            if new_name in self._profiles:
                raise ValueError(f"Profile '{new_name}' already exists")
            
            self._profiles[new_name] = self._profiles.pop(old_name)
            
            if self._current_profile == old_name:
                self._current_profile = new_name
            
            if self._base_profile == old_name:
                self._base_profile = new_name
            
            self.logger.info("Profile renamed: %s -> %s", old_name, new_name)

    def export_profile(self, name: str) -> dict[str, dict]:
        """
        Export profile configuration.
        
        Args:
            name: Profile name
            
        Returns:
            Profile configuration dictionary
            
        Raises:
            ProfileNotFoundError: If profile not found
        """
        with self._lock:
            if name not in self._profiles:
                raise ProfileNotFoundError(f"Profile '{name}' not found")
            
            return {k: v.copy() for k, v in self._profiles[name].items()}

    def import_profile(
        self,
        name: str,
        config: dict[str, dict],
    ) -> None:
        """
        Import profile configuration.
        
        Args:
            name: Profile name
            config: Profile configuration dictionary
        """
        with self._lock:
            self._profiles[name] = {
                k: v.copy() for k, v in config.items()
            }
            self.logger.info("Profile imported: %s", name)
