"""
Realtimex Modules package.

Each subdirectory here is a discoverable plugin module: a
manifest.json declaring its identity, capabilities, service
dependencies, and sandbox permissions, plus a module.py entry point
exposing a `Module` class. Modules are discovered, validated, and
loaded by the `loader` package; they never import or call each other
directly, and never instantiate services themselves.
"""
