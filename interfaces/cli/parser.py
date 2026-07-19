"""
CLI Command Parser for Realtimex.
"""

from __future__ import annotations

import shlex
from typing import Any


class CLIParser:
    """CLI command parser supporting argument grouping and flags."""

    @staticmethod
    def parse_command(command_str: str) -> dict[str, Any]:
        """
        Parse CLI command string.
        
        Args:
            command_str: Command string from user
            
        Returns:
            Parsed command dictionary with action, args, options, and raw command.
        """
        if not command_str or not command_str.strip():
            return {"action": None, "args": [], "options": {}, "raw": ""}
        
        try:
            parts = shlex.split(command_str.strip())
        except ValueError:
            # Fallback to simple split if shlex fails (e.g. unmatched quotes)
            parts = command_str.strip().split()
            
        if not parts:
            return {"action": None, "args": [], "options": {}, "raw": command_str}
            
        action = parts[0]
        args = []
        options = {}
        
        i = 1
        while i < len(parts):
            part = parts[i]
            if part.startswith('-'):
                # It's an option/flag
                name = part.lstrip('-')
                if i + 1 < len(parts) and not parts[i + 1].startswith('-'):
                    value = parts[i + 1]
                    options[name] = value
                    i += 2
                else:
                    options[name] = True
                    i += 1
            else:
                args.append(part)
                i += 1
                
        return {
            "action": action,
            "args": args,
            "options": options,
            "raw": command_str,
        }
