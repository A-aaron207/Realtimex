"""
Browser Module entry point.

Provides capabilities for simulated/headless browser interactions:
- navigate
- extract_content
- click_element
- fill_form

Note: In production this would drive a real browser (e.g. Playwright or
Selenium). For the current Kernel milestone the module uses the Model
Gateway to simulate page visits and DOM interactions so that the full
execution pipeline can be exercised without an external browser binary.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loader.module_base import ModuleEntryPoint
from services.registry import ServiceRegistry
from models.provider import ModelRequest


class Module(ModuleEntryPoint):
    """Entry point for the Browser Module."""

    module_id = "browser"
    capabilities = ["navigate", "extract_content", "click_element", "fill_form"]

    # In-process page state shared across capability calls within a task.
    def __init__(self) -> None:
        self._current_url: str | None = None
        self._page_snapshot: str = ""

    def describe(self) -> str:
        return "Provides web browser automation: page navigation, content extraction, element interaction, and form filling."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gateway(self) -> Any:
        registry = ServiceRegistry.get_instance()
        return registry.get("model_gateway").metadata["gateway"]

    def _llm(self, prompt: str, task_id: str = "browser_op") -> str:
        request = ModelRequest(
            task_id=task_id,
            request_type="generate",
            capability_required="reasoning",
            prompt=prompt,
            preferred_model="llama3-70b-8192"
        )
        response = asyncio.run(self._gateway().generate(request))
        return response.output.strip()

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def navigate(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Navigate the browser to a URL and return a simulated page snapshot."""
        url = input_data.get("url")
        if not url:
            return {"status": "FAILED", "error": "No URL provided for navigation."}

        self._current_url = url
        self._page_snapshot = self._llm(
            f"Simulate the HTML body text of a webpage at URL: '{url}'. "
            "Return a realistic plain-text snapshot (title, headings, main body paragraphs).",
            task_id="browser_navigate"
        )

        return {
            "status": "SUCCESS",
            "url": url,
            "page_snapshot": self._page_snapshot,
            "title": self._page_snapshot.splitlines()[0] if self._page_snapshot else ""
        }

    def extract_content(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Extract specific content from the current page using a CSS selector or description."""
        selector = input_data.get("selector") or input_data.get("description", "main content")
        url = input_data.get("url") or self._current_url

        if not url and not self._page_snapshot:
            return {"status": "FAILED", "error": "No page loaded. Call navigate first or provide a url."}

        if url and url != self._current_url:
            nav_result = self.navigate({"url": url})
            if nav_result["status"] == "FAILED":
                return nav_result

        extracted = self._llm(
            f"From the following page snapshot, extract content matching '{selector}':\n\n{self._page_snapshot}",
            task_id="browser_extract"
        )

        return {
            "status": "SUCCESS",
            "url": self._current_url,
            "selector": selector,
            "extracted_content": extracted
        }

    def click_element(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Simulate clicking a named element or link on the current page."""
        element = input_data.get("element") or input_data.get("text")
        url = input_data.get("url") or self._current_url

        if not element:
            return {"status": "FAILED", "error": "No element or text provided to click."}

        if url and url != self._current_url:
            nav_result = self.navigate({"url": url})
            if nav_result["status"] == "FAILED":
                return nav_result

        outcome = self._llm(
            f"Simulate clicking the element '{element}' on this page (URL: {self._current_url}).\n\n"
            f"Page snapshot:\n{self._page_snapshot}\n\n"
            "Describe what happens after the click (e.g. navigation, modal, state change).",
            task_id="browser_click"
        )

        return {
            "status": "SUCCESS",
            "element_clicked": element,
            "page_url": self._current_url,
            "outcome": outcome
        }

    def fill_form(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Simulate filling and submitting a web form."""
        fields = input_data.get("fields")  # dict: {"field_name": "value", ...}
        submit = input_data.get("submit", True)
        url = input_data.get("url") or self._current_url

        if not fields or not isinstance(fields, dict):
            return {"status": "FAILED", "error": "No form fields provided. Expected a dict of {field: value}."}

        if url and url != self._current_url:
            nav_result = self.navigate({"url": url})
            if nav_result["status"] == "FAILED":
                return nav_result

        fields_str = "\n".join(f"  {k}: {v}" for k, v in fields.items())
        outcome = self._llm(
            f"Simulate filling a web form on page (URL: {self._current_url}) with these field values:\n{fields_str}\n\n"
            f"{'Then submit the form.' if submit else 'Do not submit.'} "
            "Describe the result (e.g. success message, validation errors, redirect).",
            task_id="browser_fill_form"
        )

        return {
            "status": "SUCCESS",
            "fields_filled": fields,
            "submitted": submit,
            "url": self._current_url,
            "outcome": outcome
        }

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        if capability == "navigate":
            return self.navigate(context.input)
        elif capability == "extract_content":
            return self.extract_content(context.input)
        elif capability == "click_element":
            return self.click_element(context.input)
        elif capability == "fill_form":
            return self.fill_form(context.input)
        else:
            raise NotImplementedError(f"Capability '{capability}' not supported by Browser Module.")
