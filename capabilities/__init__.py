"""
Realtimex Capabilities package.

Provides the Capability Registry: a thread-safe lookup table mapping
capability names (e.g. "summarize_text", "web_search") to the modules
that provide them. The registry never executes capabilities -- it
only answers "who can do this?" for future orchestration components.
"""
