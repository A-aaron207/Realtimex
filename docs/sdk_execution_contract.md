# Realtimex Module SDK & Execution Contract

Modules extend the Realtimex Kernel by introducing new capabilities (e.g., file system access, terminal operations, search, vision, LLM interaction). The Module SDK defines the structural requirements and execution interface that modules must satisfy to be discovered, validated, and executed by the Kernel.

---

## 1. Module File Structure

Every Realtimex module must occupy its own directory under the `modules/` root and include at least two files:
1. `manifest.json` — Declares metadata, capabilities, dependencies, and required permissions.
2. `module.py` — Contains the Python entry point class `Module` which implements execution logic.

```text
modules/
└── my_module/
    ├── manifest.json
    └── module.py
```

---

## 2. The manifest.json Schema

The manifest file defines the configuration schema for the module.

```json
{
  "module_id": "my_module",
  "name": "My Custom Module",
  "version": "1.0.0",
  "description": "Performs custom data actions.",
  "capabilities": [
    "custom_action"
  ],
  "dependencies": {
    "services": ["model_gateway"],
    "modules": []
  },
  "permissions": {
    "filesystem": "read",
    "network": true,
    "terminal": false,
    "memory": "read_write"
  }
}
```

### Key Fields:
- `module_id`: A unique snake_case string identifier.
- `capabilities`: A list of capability strings advertised to the Kernel's `CapabilityRegistry`.
- `dependencies`: Lists of required services or other modules.
- `permissions`: Security scopes needed by this module.

---

## 3. The Execution Contract

When a task executes a capability, the worker runtime resolves the provider module and invokes the capability dynamically. The Kernel standardizes execution around the **Standardized Contract**, falling back to a **Method-Based Contract** if necessary.

### Standardized Execution Contract (Recommended)
If your `Module` class implements an `execute` method, the worker runtime invokes it according to the following parameter resolution order:

1. **Dual Parameter:** `execute(capability_name: str, context: ExecutionContext) -> Any`
2. **Single Parameter:** `execute(context: ExecutionContext) -> Any`
3. **Legacy Dual Parameter:** `execute(capability_name: str, input_data: Any) -> Any`

#### Example implementing the Standardized Contract:
```python
from loader.module_base import ModuleEntryPoint

class Module(ModuleEntryPoint):
    module_id = "my_module"
    capabilities = ["custom_action"]

    def describe(self) -> str:
        return "Custom module implementing standardized contract"

    def execute(self, capability: str, context: ExecutionContext) -> dict[str, Any]:
        if capability == "custom_action":
            # Retrieve input data
            input_text = context.input
            
            # Resolve dependencies via ServiceRegistry
            from services.registry import ServiceRegistry
            gateway = ServiceRegistry.get_instance().get("model_gateway").metadata["gateway"]
            
            return {"result": f"Executed custom_action with input: {input_text}"}
        raise NotImplementedError(f"Unsupported capability: {capability}")
```

### Method-Based Execution Contract (Fallback)
If no `execute` method is defined, the worker runtime looks for a method matching the capability name directly (e.g. `def custom_action(...)`):

1. **Input-Only Parameter:** `custom_action(input_data: Any) -> Any`
2. **Context Parameter:** `custom_action(context: ExecutionContext) -> Any`

---

## 4. "Create Your First Module" Tutorial

Let's build a simple **Text Replacer** module that replaces words in an input string.

### Step 1: Create the Directory
Create a folder called `replacer` in the `modules/` directory:
```bash
mkdir -p modules/replacer
```

### Step 2: Create manifest.json
Create `modules/replacer/manifest.json`:
```json
{
  "module_id": "replacer",
  "name": "Text Replacer Module",
  "version": "1.0.0",
  "description": "Replaces search terms with target text.",
  "capabilities": [
    "replace_text"
  ],
  "dependencies": {
    "services": [],
    "modules": []
  },
  "permissions": {
    "filesystem": "none",
    "network": false,
    "terminal": false,
    "memory": "none"
  }
}
```

### Step 3: Create module.py
Create `modules/replacer/module.py`:
```python
from typing import Any
from loader.module_base import ModuleEntryPoint

class Module(ModuleEntryPoint):
    module_id = "replacer"
    capabilities = ["replace_text"]

    def describe(self) -> str:
        return "Performs in-memory string search and replacement."

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        if capability != "replace_text":
            raise ValueError(f"Unknown capability: {capability}")

        # Extract values from input
        input_data = context.input
        if not isinstance(input_data, dict):
            raise TypeError("Input data must be a dictionary.")

        text = input_data.get("text", "")
        old = input_data.get("old", "")
        new = input_data.get("new", "")

        replaced = text.replace(old, new)
        return {
            "output": replaced,
            "replacements_made": text.count(old)
        }
```

### Step 4: Verification
Reboot the Realtimex Kernel. The Module Loader will automatically discover the `replacer` directory, validate `manifest.json`, load `module.py`, and register the `replace_text` capability. You can verify it by running performance benchmarks or submitting a task containing the goal `"replace_text"`.
