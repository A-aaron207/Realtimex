"""
Module Generator for Realtimex MDK.

Scaffolds directories and starter templates for modules, providers, and workers.
"""

from __future__ import annotations

import os
import json
from typing import Any, Optional

from sdk.generator.manifest_generator import generate_manifest
from sdk.exceptions import GeneratorError


def scaffold_module(
    name: str,
    output_dir: str,
    module_type: str = "module",
    event_bus: Any = None,
) -> str:
    """
    Scaffold a new Realtimex module directory structure and starter code.
    
    Args:
        name: Name of module (alphanumeric/hyphen/underscore)
        output_dir: Directory where the scaffold should be placed
        module_type: Extension type ('module', 'worker', 'provider', 'service')
        event_bus: Optional Event Bus for event-driven updates
        
    Returns:
        Absolute path to the created module directory
        
    Raises:
        GeneratorError: If output path already exists
    """
    # Normalize name to lower-snake-case for folder/file names
    clean_name = name.lower().replace(" ", "_")
    module_dir = os.path.join(output_dir, clean_name)
    
    if os.path.exists(module_dir):
        raise GeneratorError(f"Scaffolding target path already exists: {module_dir}")

    try:
        # Create directories
        os.makedirs(module_dir, exist_ok=True)
        os.makedirs(os.path.join(module_dir, "tests"), exist_ok=True)
        os.makedirs(os.path.join(module_dir, "prompts"), exist_ok=True)
        os.makedirs(os.path.join(module_dir, "assets"), exist_ok=True)

        # Determine entrypoint file name
        entrypoint = f"{clean_name}.py"

        # Create manifest
        manifest = generate_manifest(
            name=clean_name,
            module_type=module_type,
            entrypoint=entrypoint,
        )
        with open(os.path.join(module_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4)

        # Format Class Name (PascalCase)
        class_name = "".join(word.title() for word in clean_name.split("_") if word)

        # Generate class templates
        if module_type == "module":
            code = f"""from sdk.core.module import BaseModule, ModuleContext
from typing import Any


class {class_name}Module(BaseModule):
    \"\"\"{class_name} module implementation.\"\"\"

    def initialize(self) -> None:
        self.context.log("INFO", "Initializing {clean_name} module")

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.context.log("INFO", "Executing {clean_name} module")
        return {{"status": "success", "message": "Hello from {clean_name} Module!"}}

    def shutdown(self) -> None:
        self.context.log("INFO", "Shutting down {clean_name} module")
"""
        elif module_type == "worker":
            code = f"""from sdk.core.worker import BaseWorker
from typing import Any


class {class_name}Worker(BaseWorker):
    \"\"\"{class_name} worker implementation.\"\"\"

    def run_task(self, task: Any) -> Any:
        self.context.log("INFO", "Running task on {clean_name} worker")
        return {{"status": "complete", "worker": "{clean_name}"}}
"""
        elif module_type == "provider":
            code = f"""from sdk.core.provider import BaseProvider
from typing import Any


class {class_name}Provider(BaseProvider):
    \"\"\"{class_name} LLM Provider implementation.\"\"\"

    def generate(self, prompt: str, **kwargs: Any) -> Any:
        self.context.log("INFO", "Generating content via {clean_name} provider")
        return f"Response to: {{prompt}}"
"""
        else:  # Generic base fallback
            code = f"""from sdk.core.module import BaseModule, ModuleContext
from typing import Any


class {class_name}(BaseModule):
    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {{"status": "success"}}
"""

        # Write Python entrypoint
        with open(os.path.join(module_dir, entrypoint), "w", encoding="utf-8") as f:
            f.write(code.lstrip())

        # Write README.md
        readme = f"""# {class_name}

Realtimex {module_type.title()} scaffold.

## Structure
- `manifest.json`: Configuration manifest
- `{entrypoint}`: Primary class logic
- `tests/`: Module tests
- `prompts/`: Prompts and templates
- `assets/`: Static resources
"""
        with open(os.path.join(module_dir, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme.lstrip())

        # Write a dummy test
        dummy_test = f"""import pytest
from unittest.mock import MagicMock
from sdk.core.module import ModuleContext

def test_{clean_name}_scaffold():
    assert True
"""
        with open(os.path.join(module_dir, "tests", f"test_{clean_name}.py"), "w", encoding="utf-8") as f:
            f.write(dummy_test.lstrip())

        # Emit ModuleCreated event
        if event_bus:
            try:
                from events.event import Event, EventPriority
                event_bus.publish(
                    Event(
                        name="ModuleCreated",
                        source="sdk.generator",
                        payload={
                            "name": clean_name,
                            "type": module_type,
                            "path": os.path.abspath(module_dir),
                        },
                        priority=EventPriority.NORMAL,
                    )
                )
            except Exception:
                pass

        return os.path.abspath(module_dir)

    except Exception as e:
        # Cleanup partially scaffolded dir if created
        if os.path.exists(module_dir):
            try:
                import shutil
                shutil.rmtree(module_dir)
            except Exception:
                pass
        raise GeneratorError(f"Failed to scaffold module: {e}") from e
