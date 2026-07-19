"""
Vision Module entry point.

Provides image understanding and OCR capabilities:
- analyze_image       — describe and classify image content
- extract_text        — OCR: extract text from an image file
- describe_screenshot — interpret a UI screenshot into structured observations
- compare_images      — compare two images and report differences

Note: Production integration would use a multimodal model (e.g. Gemini Vision,
GPT-4o) or a dedicated OCR library (Tesseract). For the current Kernel
milestone the Model Gateway simulates the vision responses, keeping the full
execution pipeline exercisable without external vision dependencies.
"""

from __future__ import annotations

import asyncio
import os
import base64
from pathlib import Path
from typing import Any

from loader.module_base import ModuleEntryPoint
from services.registry import ServiceRegistry
from models.provider import ModelRequest


class Module(ModuleEntryPoint):
    """Entry point for the Vision Module."""

    module_id = "vision"
    capabilities = ["analyze_image", "extract_text", "describe_screenshot", "compare_images"]

    def describe(self) -> str:
        return "Provides image analysis, OCR text extraction, screenshot interpretation, and visual diff capabilities."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gateway(self) -> Any:
        registry = ServiceRegistry.get_instance()
        return registry.get("model_gateway").metadata["gateway"]

    def _llm(self, prompt: str, task_id: str = "vision_op") -> str:
        request = ModelRequest(
            task_id=task_id,
            request_type="generate",
            capability_required="reasoning",
            prompt=prompt,
            preferred_model="llama3-70b-8192"
        )
        response = asyncio.run(self._gateway().generate(request))
        return response.output.strip()

    def _image_context(self, path: str | None) -> str:
        """Return a concise image descriptor for the LLM prompt."""
        if not path:
            return "[no image path provided]"
        p = Path(path)
        if not p.is_file():
            return f"[image not found: {path}]"
        size_kb = round(p.stat().st_size / 1024, 1)
        return f"[image file: {p.name}, size: {size_kb} KB, format: {p.suffix.lstrip('.').upper()}]"

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def analyze_image(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze an image and return objects, labels, and a scene description."""
        path = input_data.get("path") or input_data.get("image_path")
        question = input_data.get("question", "What is in this image?")

        if not path:
            return {"status": "FAILED", "error": "No image path provided."}

        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return {"status": "FAILED", "error": f"Image not found: {path}"}

        img_ctx = self._image_context(path)
        analysis = self._llm(
            f"You are a vision AI. Given the following image context: {img_ctx}\n\n"
            f"Question: {question}\n\n"
            "Provide: (1) a scene description, (2) a list of detected objects/labels, "
            "(3) dominant colors, (4) overall sentiment/tone.",
            task_id="vision_analyze"
        )

        return {
            "status": "SUCCESS",
            "path": path,
            "question": question,
            "analysis": analysis
        }

    def extract_text(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Extract all readable text from an image (OCR)."""
        path = input_data.get("path") or input_data.get("image_path")
        language = input_data.get("language", "en")

        if not path:
            return {"status": "FAILED", "error": "No image path provided."}

        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return {"status": "FAILED", "error": f"Image not found: {path}"}

        img_ctx = self._image_context(path)
        extracted = self._llm(
            f"You are an OCR engine. Given the image context: {img_ctx} (language hint: {language})\n\n"
            "Extract and return all readable text exactly as it appears in the image. "
            "Preserve line breaks and formatting as best as possible.",
            task_id="vision_ocr"
        )

        return {
            "status": "SUCCESS",
            "path": path,
            "language": language,
            "extracted_text": extracted
        }

    def describe_screenshot(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Interpret a UI screenshot and return structured observations."""
        path = input_data.get("path") or input_data.get("screenshot_path")
        context = input_data.get("context", "")  # optional app/page context hint

        if not path:
            return {"status": "FAILED", "error": "No screenshot path provided."}

        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return {"status": "FAILED", "error": f"Screenshot not found: {path}"}

        img_ctx = self._image_context(path)
        context_hint = f" Context hint: {context}." if context else ""
        description = self._llm(
            f"You are a UI analyst.{context_hint} Given screenshot: {img_ctx}\n\n"
            "Describe: (1) the application type, (2) visible UI elements (buttons, forms, menus), "
            "(3) the current page/state, (4) any errors or alerts visible, "
            "(5) suggested next user action.",
            task_id="vision_screenshot"
        )

        return {
            "status": "SUCCESS",
            "path": path,
            "ui_description": description
        }

    def compare_images(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Compare two images and report visual differences."""
        path_a = input_data.get("path_a") or input_data.get("image_a")
        path_b = input_data.get("path_b") or input_data.get("image_b")

        if not path_a or not path_b:
            return {"status": "FAILED", "error": "Both path_a and path_b are required."}

        path_a = os.path.abspath(path_a)
        path_b = os.path.abspath(path_b)

        for p in [path_a, path_b]:
            if not os.path.isfile(p):
                return {"status": "FAILED", "error": f"Image not found: {p}"}

        ctx_a = self._image_context(path_a)
        ctx_b = self._image_context(path_b)

        diff = self._llm(
            f"You are a visual diff engine. Compare these two images:\n"
            f"  Image A: {ctx_a}\n"
            f"  Image B: {ctx_b}\n\n"
            "Report: (1) key similarities, (2) key differences, "
            "(3) which image appears newer or more complete, (4) a similarity score 0-100.",
            task_id="vision_compare"
        )

        return {
            "status": "SUCCESS",
            "path_a": path_a,
            "path_b": path_b,
            "comparison": diff
        }

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        dispatch = {
            "analyze_image": self.analyze_image,
            "extract_text": self.extract_text,
            "describe_screenshot": self.describe_screenshot,
            "compare_images": self.compare_images,
        }
        if capability not in dispatch:
            raise NotImplementedError(f"Capability '{capability}' not supported by Vision Module.")
        return dispatch[capability](context.input)
