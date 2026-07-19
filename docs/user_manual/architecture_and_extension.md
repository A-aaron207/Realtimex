# User Manual — Architecture & Extension

This document explains the runtime lifecycle of Realtimex and how to extend it by authoring custom modules.

---

## 🏗️ Architecture Summary

Realtimex utilizes a topological DAG scheduler to run boot components in parallel.

```text
Boot Sequence
  ├── Configuration & Logger
  ├── Event Manager & Service Registry
  ├── Task & Memory Systems (Async Background Recovery)
  └── Module Loader Discovery
```

* **Concurrency**: Systems like task caching, memory indexing, and workflow lookups are loaded concurrently using `ThreadPoolExecutor`.
* **State Recovery**: Unfinished tasks are recovered asynchronously in a background daemon worker to avoid blocking the critical path to a `READY` state.

---

## 🔌 Authoring Custom Modules

To add a new capability module to Realtimex, create a folder under `modules/` (e.g. `modules/my_module/`) containing:
1. `manifest.json`
2. `my_module.py`

### 1. The Module Manifest (`manifest.json`)
The module loader validates the JSON schema of your module's manifest file at boot time:

```json
{
  "id": "my_module",
  "name": "My Custom Module",
  "version": "1.0.0",
  "description": "Exposes custom filesystem actions",
  "entrypoint": "my_module.py",
  "capabilities": [
    "custom_read"
  ],
  "permissions": {
    "filesystem": {
      "read": ["/tmp"]
    }
  }
}
```

### 2. The Module Logic (`my_module.py`)
Expose the capabilities matching the manifest declarations. Realtimex inspects functions dynamically:

```python
class MyModule:
    def custom_read(self, path: str) -> str:
        # Implements 'custom_read' capability
        with open(path, "r") as f:
            return f.read()
```

---

## 🔒 Permission Sandbox

All module capabilities undergo policy validation through the `PermissionManager`:
- Policies default to **deny** if not explicitly allowed.
- Approved decisions are stored in a thread-safe local cache (`PermissionCache`) to optimize verification speed during high-frequency workflow steps.
