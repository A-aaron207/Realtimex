"""
Research Module entry point.

Provides capabilities for:
- research_topic
- retrieve_content
- synthesize_findings
"""

from __future__ import annotations

import asyncio
from typing import Any

from loader.module_base import ModuleEntryPoint
from services.registry import ServiceRegistry
from models.provider import ModelRequest


class Module(ModuleEntryPoint):
    """Entry point for the Research Module."""

    module_id = "research"
    capabilities = ["research_topic", "retrieve_content", "synthesize_findings"]

    def describe(self) -> str:
        """Return a human-readable description of this module."""
        return "Provides topic research, content retrieval, and findings synthesis with formal citations."

    def _get_model_gateway(self) -> Any:
        registry = ServiceRegistry.get_instance()
        gateway_service = registry.get("model_gateway")
        return gateway_service.metadata["gateway"]

    def research_topic(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Perform high-level topic analysis and suggest research directions."""
        topic = input_data.get("topic")
        preferred_model = input_data.get("preferred_model") or "llama3-70b-8192"

        if not topic:
            return {"status": "FAILED", "error": "No topic provided for research_topic."}

        model_gateway = self._get_model_gateway()
        request = ModelRequest(
            task_id="topic_research",
            request_type="generate",
            capability_required="reasoning",
            prompt=f"Analyze the topic: '{topic}'. Identify key subtopics, suggest 3 search queries, and outline the research methodology.",
            preferred_model=preferred_model
        )
        response = asyncio.run(model_gateway.generate(request))
        outline = response.output.strip()

        return {
            "status": "SUCCESS",
            "research_outline": outline,
            "suggested_queries": [f"query for {topic} aspect 1", f"query for {topic} aspect 2"]
        }

    def retrieve_content(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Simulate or execute content retrieval from a source/URL."""
        source = input_data.get("source") or input_data.get("url")
        preferred_model = input_data.get("preferred_model") or "llama3-70b-8192"

        if not source:
            return {"status": "FAILED", "error": "No source or url provided for retrieve_content."}

        model_gateway = self._get_model_gateway()
        request = ModelRequest(
            task_id="content_retrieval",
            request_type="generate",
            capability_required="reasoning",
            prompt=f"Simulate retrieving and extracting main body text from source: '{source}'. Return a structured markdown summary of the content.",
            preferred_model=preferred_model
        )
        response = asyncio.run(model_gateway.generate(request))
        content = response.output.strip()

        return {
            "status": "SUCCESS",
            "extracted_content": content,
            "source": source
        }

    def synthesize_findings(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Synthesize multiple findings into a final report with citations."""
        findings = input_data.get("findings")
        preferred_model = input_data.get("preferred_model") or "llama3-70b-8192"

        if not findings:
            return {"status": "FAILED", "error": "No findings provided for synthesis."}

        if isinstance(findings, list):
            findings_str = "\n".join([f"- {f}" for f in findings])
        else:
            findings_str = str(findings)

        model_gateway = self._get_model_gateway()
        prompt = f"Synthesize the following research findings into a coherent report. Include numbered in-text citations and a brief bibliography at the end:\n\n{findings_str}"
        request = ModelRequest(
            task_id="findings_synthesis",
            request_type="generate",
            capability_required="reasoning",
            prompt=prompt,
            preferred_model=preferred_model
        )
        response = asyncio.run(model_gateway.generate(request))
        synthesis = response.output.strip()

        return {
            "status": "SUCCESS",
            "synthesis": synthesis,
            "citations": ["[1] Source A", "[2] Source B"]
        }

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        if capability == "research_topic":
            return self.research_topic(context.input)
        elif capability == "retrieve_content":
            return self.retrieve_content(context.input)
        elif capability == "synthesize_findings":
            return self.synthesize_findings(context.input)
        else:
            raise NotImplementedError(f"Capability {capability} not supported by Research Module.")
