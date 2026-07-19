"""
Realtimex Loader package.

Implements the module discovery, manifest validation, and dynamic
loading pipeline. The loader scans the `modules/` directory, validates
each module's manifest.json against the Realtimex schema, imports its
module.py entry point, and registers its declared capabilities and
service dependencies -- isolating any individual module's failure so
the Kernel keeps running.
"""
