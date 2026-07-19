"""
Platform Abstraction Layer for Realtimex.
Exposes unified platform adapters for Linux, Windows, and Raspberry Pi targets.
"""

from __future__ import annotations

from platform_adapter.base import BasePlatform
from platform_adapter.factory import Platform

__all__ = ["BasePlatform", "Platform"]
