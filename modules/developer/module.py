"""
Developer Module entry point.

Provides capabilities for:
- generate_code
- refactor_code
- debug_code
- run_tests
"""

from __future__ import annotations

import os
import subprocess
import asyncio
from typing import Any

from loader.module_base import ModuleEntryPoint
from services.registry import ServiceRegistry
from models.provider import ModelRequest


class Module(ModuleEntryPoint):
    """Entry point for the Developer Module."""

    module_id = "developer"
    capabilities = ["generate_code", "refactor_code", "debug_code", "run_tests"]

    def describe(self) -> str:
        """Return a human-readable description of this module."""
        return "Provides code generation, refactoring, debugging, and test runner capabilities."

    def _get_model_gateway(self) -> Any:
        registry = ServiceRegistry.get_instance()
        gateway_service = registry.get("model_gateway")
        return gateway_service.metadata["gateway"]

    def generate_code(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate code using model gateway and optionally save to file."""
        prompt = input_data.get("prompt")
        file_path = input_data.get("file_path")
        preferred_model = input_data.get("preferred_model") or "llama3-70b-8192"

        if not prompt:
            return {"status": "FAILED", "error": "No prompt provided for generate_code."}

        model_gateway = self._get_model_gateway()
        request = ModelRequest(
            task_id="code_generation",
            request_type="generate",
            capability_required="reasoning",
            prompt=f"Generate programming code matching this requirement:\n{prompt}\nOutput ONLY the raw code.",
            preferred_model=preferred_model
        )
        response = asyncio.run(model_gateway.generate(request))
        code = response.output.strip()

        # Clean markdown wrappers if present
        for fence in ["```python", "```javascript", "```html", "```css", "```json", "```"]:
            if code.startswith(fence):
                code = code[len(fence):]
            if code.endswith("```"):
                code = code[:-3]
        code = code.strip()

        if file_path:
            abs_path = os.path.abspath(file_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            try:
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(code)
                return {
                    "status": "SUCCESS",
                    "code": code,
                    "file_path": abs_path,
                    "bytes_written": len(code)
                }
            except Exception as e:
                return {"status": "FAILED", "error": f"Failed to write generated code to {file_path}: {e}"}

        return {"status": "SUCCESS", "code": code}

    def refactor_code(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Refactor code based on instructions."""
        code = input_data.get("code")
        file_path = input_data.get("file_path")
        instructions = input_data.get("instructions")
        preferred_model = input_data.get("preferred_model") or "llama3-70b-8192"

        if not instructions:
            return {"status": "FAILED", "error": "No instructions provided for refactor_code."}

        if file_path:
            abs_path = os.path.abspath(file_path)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    code = f.read()
            except Exception as e:
                return {"status": "FAILED", "error": f"Failed to read file for refactoring {file_path}: {e}"}

        if not code:
            return {"status": "FAILED", "error": "No code provided or read for refactoring."}

        model_gateway = self._get_model_gateway()
        prompt = f"Refactor the following code based on these instructions:\nInstructions: {instructions}\n\nCode:\n{code}\n\nOutput ONLY the refactored code."
        request = ModelRequest(
            task_id="code_refactoring",
            request_type="generate",
            capability_required="reasoning",
            prompt=prompt,
            preferred_model=preferred_model
        )
        response = asyncio.run(model_gateway.generate(request))
        refactored = response.output.strip()

        for fence in ["```python", "```javascript", "```html", "```css", "```json", "```"]:
            if refactored.startswith(fence):
                refactored = refactored[len(fence):]
            if refactored.endswith("```"):
                refactored = refactored[:-3]
        refactored = refactored.strip()

        if file_path:
            try:
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(refactored)
                return {
                    "status": "SUCCESS",
                    "refactored_code": refactored,
                    "file_path": abs_path,
                    "bytes_written": len(refactored)
                }
            except Exception as e:
                return {"status": "FAILED", "error": f"Failed to save refactored code to {file_path}: {e}"}

        return {"status": "SUCCESS", "refactored_code": refactored}

    def debug_code(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Debug code using an error message and return/apply fixed code."""
        code = input_data.get("code")
        file_path = input_data.get("file_path")
        error_message = input_data.get("error_message")
        preferred_model = input_data.get("preferred_model") or "llama3-70b-8192"

        if not error_message:
            return {"status": "FAILED", "error": "No error_message provided for debugging."}

        if file_path:
            abs_path = os.path.abspath(file_path)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    code = f.read()
            except Exception as e:
                return {"status": "FAILED", "error": f"Failed to read file for debugging {file_path}: {e}"}

        if not code:
            return {"status": "FAILED", "error": "No code provided or read for debugging."}

        model_gateway = self._get_model_gateway()
        prompt = f"Fix the errors in the following code.\nError message: {error_message}\n\nCode:\n{code}\n\nOutput ONLY the corrected code."
        request = ModelRequest(
            task_id="code_debugging",
            request_type="generate",
            capability_required="reasoning",
            prompt=prompt,
            preferred_model=preferred_model
        )
        response = asyncio.run(model_gateway.generate(request))
        fixed = response.output.strip()

        for fence in ["```python", "```javascript", "```html", "```css", "```json", "```"]:
            if fixed.startswith(fence):
                fixed = fixed[len(fence):]
            if fixed.endswith("```"):
                fixed = fixed[:-3]
        fixed = fixed.strip()

        if file_path:
            try:
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(fixed)
                return {
                    "status": "SUCCESS",
                    "fixed_code": fixed,
                    "file_path": abs_path,
                    "bytes_written": len(fixed)
                }
            except Exception as e:
                return {"status": "FAILED", "error": f"Failed to save fixed code to {file_path}: {e}"}

        return {"status": "SUCCESS", "fixed_code": fixed}

    def run_tests(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute test commands in a subprocess and return outputs."""
        test_command = input_data.get("test_command")
        cwd = input_data.get("cwd")

        if not test_command:
            return {"status": "FAILED", "error": "No test_command provided."}

        if cwd:
            cwd = os.path.abspath(cwd)
        else:
            cwd = os.getcwd()

        try:
            result = subprocess.run(
                test_command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30.0
            )
            return {
                "status": "SUCCESS" if result.returncode == 0 else "FAILED",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired as e:
            return {
                "status": "FAILED",
                "error": "Test command execution timed out.",
                "stdout": e.stdout or "",
                "stderr": e.stderr or ""
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": f"Failed to run test command: {e}"
            }

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        if capability == "generate_code":
            return self.generate_code(context.input)
        elif capability == "refactor_code":
            return self.refactor_code(context.input)
        elif capability == "debug_code":
            return self.debug_code(context.input)
        elif capability == "run_tests":
            return self.run_tests(context.input)
        else:
            raise NotImplementedError(f"Capability {capability} not supported by Developer Module.")
