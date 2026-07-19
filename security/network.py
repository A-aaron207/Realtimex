"""
Network Isolation for Realtimex.

Checks outbound connections based on domain, localhost, proxy, and NetworkPolicy rules.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from security.policies import NetworkPolicy


class NetworkIsolator:
    """Enforces connection restrictions based on domain lists and network profiles."""

    def __init__(
        self,
        policy: str = NetworkPolicy.NO_NETWORK,
        approved_domains: Optional[list[str]] = None,
        proxy_address: Optional[str] = None,
    ) -> None:
        """
        Initialize NetworkIsolator.
        
        Args:
            policy: NetworkPolicy code
            approved_domains: List of domains allowed for APPROVED_DOMAINS checks
            proxy_address: Optional proxy endpoint configured
        """
        self.policy = policy
        self.approved_domains = [d.lower() for d in (approved_domains or [])]
        self.proxy_address = proxy_address

    def is_connection_allowed(self, url_or_host: str) -> bool:
        """
        Check if connecting to the URL/host is permitted by the policy.
        
        Args:
            url_or_host: Destination string (e.g. 'https://api.github.com' or 'localhost')
            
        Returns:
            True if permitted, False otherwise
        """
        if self.policy == NetworkPolicy.FULL_NETWORK:
            return True

        if self.policy == NetworkPolicy.NO_NETWORK:
            return False

        # Extract hostname/netloc
        parsed = urlparse(url_or_host)
        host = parsed.netloc or parsed.path
        if ":" in host:
            host = host.split(":")[0]
        host = host.lower().strip()

        if self.policy == NetworkPolicy.LOCALHOST_ONLY:
            return host in ("localhost", "127.0.0.1", "::1")

        if self.policy == NetworkPolicy.APPROVED_DOMAINS:
            for domain in self.approved_domains:
                # Direct match or subdomain match (e.g. sub.example.com vs example.com)
                if host == domain or host.endswith("." + domain):
                    return True
            return False

        return False
