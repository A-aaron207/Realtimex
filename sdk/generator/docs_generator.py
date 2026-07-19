"""
Documentation Generator for Realtimex MDK.

Generates API documentation, manifest references, and module details.
"""

from __future__ import annotations

import os


def generate_docs(output_path: str) -> str:
    """
    Generate developer documentation for Realtimex modules.
    
    Args:
        output_path: File path to save the generated markdown file
        
    Returns:
        Absolute path to the created markdown file
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    markdown = """# Realtimex Extension Development Reference

This guide covers building, configuring, and packaging modules for the Realtimex Kernel.

---

## 1. Manifest JSON Reference
Every extension must provide a `manifest.json` file in its root folder.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | String | **Yes** | Lowercase alphanumeric extension name. |
| `version` | String | **Yes** | Semantic version identifier (e.g. `1.0.0`). |
| `type` | String | **Yes** | Extension category: `module`, `worker`, `provider`, or `service`. |
| `entrypoint` | String | **Yes** | Source code entrypoint script path ending in `.py`. |
| `dependencies` | Object | No | Map of key-value package versions required. |
| `permissions` | Array | No | Permission tokens requested by this extension. |
| `capabilities` | Array | No | Capability specifications provided. |

---

## 2. Developer Base Classes
Extensions inherit from the official MDK base classes:

### BaseModule
Core extension module responding to action payloads.
```python
from sdk.core.module import BaseModule, ModuleContext
from typing import Any

class MyModule(BaseModule):
    def initialize(self) -> None:
        pass

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.context.log("INFO", "Running MyModule")
        return {"status": "success"}

    def shutdown(self) -> None:
        pass
```

### BaseWorker
Background orchestrator executing tasks.
```python
from sdk.core.worker import BaseWorker
from typing import Any

class MyWorker(BaseWorker):
    def run_task(self, task: Any) -> Any:
        return "task output"
```

### BaseProvider
Integrates third-party LLM providers.
```python
from sdk.core.provider import BaseProvider
from typing import Any

class MyProvider(BaseProvider):
    def generate(self, prompt: str, **kwargs: Any) -> Any:
        return f"Output: {prompt}"
```
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown.strip())

    return os.path.abspath(output_path)
