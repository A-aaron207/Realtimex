"""
Authentication and authorization for Realtimex Interface Layer.

Handles user authentication, token management, and permission verification.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional


class AuthenticationManager:
    """
    Manages user authentication and token generation/validation.
    
    Supports:
    - Token-based authentication
    - Token expiration
    - Token refresh
    """

    def __init__(
        self,
        token_ttl_hours: int = 24,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize AuthenticationManager.
        
        Args:
            token_ttl_hours: Token time-to-live in hours
            logger: Optional logger instance
        """
        self.token_ttl = timedelta(hours=token_ttl_hours)
        self.logger = logger or logging.getLogger("realtimex.interfaces.auth")
        self._tokens: dict[str, dict] = {}  # token -> {user_id, created_at, expires_at}
        self._lock = threading.RLock()

    def generate_token(self, user_id: str) -> str:
        """
        Generate authentication token for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Authentication token
        """
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        
        with self._lock:
            self._tokens[token] = {
                "user_id": user_id,
                "created_at": now,
                "expires_at": now + self.token_ttl,
            }
        
        self.logger.info("Token generated for user: %s", user_id)
        return token

    def validate_token(self, token: str) -> Optional[str]:
        """
        Validate authentication token.
        
        Args:
            token: Token to validate
            
        Returns:
            User ID if valid, None otherwise
        """
        with self._lock:
            token_data = self._tokens.get(token)
            
            if not token_data:
                return None
            
            now = datetime.now(timezone.utc)
            if now > token_data["expires_at"]:
                del self._tokens[token]
                return None
            
            return token_data["user_id"]

    def refresh_token(self, token: str) -> Optional[str]:
        """
        Refresh an existing token.
        
        Args:
            token: Token to refresh
            
        Returns:
            New token if refresh successful, None otherwise
        """
        with self._lock:
            user_id = self.validate_token(token)
            if not user_id:
                return None
            
            # Remove old token
            del self._tokens[token]
            
            # Generate new token
            new_token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc)
            self._tokens[new_token] = {
                "user_id": user_id,
                "created_at": now,
                "expires_at": now + self.token_ttl,
            }
            
            self.logger.info("Token refreshed for user: %s", user_id)
            return new_token

    def revoke_token(self, token: str) -> bool:
        """
        Revoke an authentication token.
        
        Args:
            token: Token to revoke
            
        Returns:
            True if revoked, False if not found
        """
        with self._lock:
            if token in self._tokens:
                del self._tokens[token]
                return True
        return False

    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens.
        
        Returns:
            Number of tokens removed
        """
        removed = 0
        now = datetime.now(timezone.utc)
        
        with self._lock:
            expired_tokens = [
                token for token, data in self._tokens.items()
                if now > data["expires_at"]
            ]
            for token in expired_tokens:
                del self._tokens[token]
                removed += 1
        
        if removed > 0:
            self.logger.info("Cleaned up %d expired tokens", removed)
        
        return removed


class AuthorizationManager:
    """
    Manages user permissions and authorization.
    
    Supports:
    - Role-based access control (RBAC)
    - Permission checking
    - Dynamic permission updates
    """

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ) -> None:
        """
        Initialize AuthorizationManager.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("realtimex.interfaces.authz")
        self._user_roles: dict[str, set[str]] = {}  # user_id -> {role, ...}
        self._role_permissions: dict[str, set[str]] = {}  # role -> {permission, ...}
        self._lock = threading.RLock()
        
        # Initialize default roles
        self._init_default_roles()

    def _init_default_roles(self) -> None:
        """Initialize default roles."""
        with self._lock:
            # Admin: all permissions
            self._role_permissions["admin"] = {
                "task.create",
                "task.read",
                "task.update",
                "task.delete",
                "workflow.create",
                "workflow.read",
                "workflow.update",
                "workflow.delete",
                "memory.read",
                "memory.write",
                "system.admin",
            }
            
            # User: basic permissions
            self._role_permissions["user"] = {
                "task.create",
                "task.read",
                "task.update",
                "workflow.read",
                "memory.read",
            }
            
            # Viewer: read-only permissions
            self._role_permissions["viewer"] = {
                "task.read",
                "workflow.read",
                "memory.read",
            }

    def assign_role(self, user_id: str, role: str) -> bool:
        """
        Assign role to user.
        
        Args:
            user_id: User identifier
            role: Role name
            
        Returns:
            True if assigned, False if role not found
        """
        with self._lock:
            if role not in self._role_permissions:
                return False
            
            if user_id not in self._user_roles:
                self._user_roles[user_id] = set()
            
            self._user_roles[user_id].add(role)
            self.logger.info("Role '%s' assigned to user '%s'", role, user_id)
            return True

    def revoke_role(self, user_id: str, role: str) -> bool:
        """
        Revoke role from user.
        
        Args:
            user_id: User identifier
            role: Role name
            
        Returns:
            True if revoked, False if not assigned
        """
        with self._lock:
            if user_id in self._user_roles:
                if role in self._user_roles[user_id]:
                    self._user_roles[user_id].remove(role)
                    self.logger.info("Role '%s' revoked from user '%s'", role, user_id)
                    return True
        
        return False

    def check_permission(self, user_id: str, permission: str) -> bool:
        """
        Check if user has permission.
        
        Args:
            user_id: User identifier
            permission: Permission name
            
        Returns:
            True if user has permission
        """
        with self._lock:
            roles = self._user_roles.get(user_id, set())
            
            for role in roles:
                permissions = self._role_permissions.get(role, set())
                if permission in permissions:
                    return True
        
        return False

    def get_user_permissions(self, user_id: str) -> set[str]:
        """
        Get all permissions for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Set of permissions
        """
        permissions = set()
        
        with self._lock:
            roles = self._user_roles.get(user_id, set())
            
            for role in roles:
                permissions.update(self._role_permissions.get(role, set()))
        
        return permissions

    def get_user_roles(self, user_id: str) -> set[str]:
        """
        Get user roles.
        
        Args:
            user_id: User identifier
            
        Returns:
            Set of role names
        """
        with self._lock:
            return self._user_roles.get(user_id, set()).copy()

    def create_role(self, role: str, permissions: set[str]) -> bool:
        """
        Create new role.
        
        Args:
            role: Role name
            permissions: Set of permissions for role
            
        Returns:
            True if created, False if already exists
        """
        with self._lock:
            if role in self._role_permissions:
                return False
            
            self._role_permissions[role] = permissions.copy()
            self.logger.info("Role created: %s with %d permissions", role, len(permissions))
            return True

    def update_role_permissions(self, role: str, permissions: set[str]) -> bool:
        """
        Update permissions for a role.
        
        Args:
            role: Role name
            permissions: New set of permissions
            
        Returns:
            True if updated, False if role not found
        """
        with self._lock:
            if role not in self._role_permissions:
                return False
            
            self._role_permissions[role] = permissions.copy()
            self.logger.info("Role updated: %s with %d permissions", role, len(permissions))
            return True
