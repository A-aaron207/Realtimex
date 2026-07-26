"""
Extensible Workflow Planner that converts user goals into execution step graphs.
"""

from __future__ import annotations

import json
import asyncio
from typing import Any

from workflow.step import StepState, WorkflowStep


class WorkflowPlanner:
    """
    Base class for workflow planners. Planners map task goals to step sequences.
    """

    def plan(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """
        Generate execution steps for a workflow.

        Args:
            workflow_id: Unique identifier for the parent workflow.
            goal: The task goal description.

        Returns:
            List of generated WorkflowStep instances.
        """
        raise NotImplementedError("Planners must implement the plan method.")


class RuleBasedWorkflowPlanner(WorkflowPlanner):
    """
    Extensible rule-based planner analyzing goal keywords to construct realistic steps.
    """

    def plan(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        goal_lower = goal.lower().strip()

        # 1. Deterministic template rules evaluated first
        if "permission failure" in goal_lower:
            return self._build_permission_fail_workflow(workflow_id, goal)
        if "transient failure" in goal_lower:
            return self._build_transient_fail_workflow(workflow_id, goal)
        if "resource failure" in goal_lower:
            return self._build_resource_fail_workflow(workflow_id, goal)
        if "provider failure" in goal_lower:
            return self._build_provider_fail_workflow(workflow_id, goal)
        if "repair" in goal_lower or "permanent failure" in goal_lower:
            return self._build_repair_workflow(workflow_id, goal)
        if "parallel" in goal_lower:
            return self._build_parallel_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["retry", "recovery", "interruption", "fail"]):
            return self._build_retry_workflow(workflow_id, goal)
        if "permission" in goal_lower:
            return self._build_permission_workflow(workflow_id, goal)

        # Prefer native tool execution over LLM reasoning
        native_steps = self._build_native_tool_workflow(workflow_id, goal)
        if native_steps is not None:
            return native_steps
            
        # Check for compound code and save requests
        is_code_request = any(kw in goal_lower for kw in ["write", "code", "create", "make", "generate", "build", "refactor"]) and any(kw in goal_lower for kw in ["python", "html", "css", "calculator", "function", "program", "script"])
        is_save_request = "save" in goal_lower or "write file" in goal_lower or "write to file" in goal_lower
        if is_code_request and is_save_request:
            return self._build_code_and_save_workflow(workflow_id, goal)
            
        if "save" in goal_lower or "write file" in goal_lower or "write to file" in goal_lower:
            return self._build_write_file_workflow(workflow_id, goal)
        if "multi-step" in goal_lower or "read and summarize" in goal_lower:
            return self._build_multistep_workflow(workflow_id, goal)
        if "read local file" in goal_lower or "read file" in goal_lower:
            return self._build_read_file_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["python", "generate code", "coding", "function to"]):
            return self._build_generate_code_workflow(workflow_id, goal)
        if "summarize" in goal_lower or "summarization" in goal_lower:
            return self._build_summarization_workflow(workflow_id, goal)
        if "research" in goal_lower or "search" in goal_lower:
            return self._build_research_workflow(workflow_id, goal)
        if any(kw in goal_lower or kw == goal_lower for kw in ["explain", "answer", "question", "what", "how", "recursion", "hello", "hi", "hey", "help", "hello?"]):
            return self._build_answer_question_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["portfolio"]):
            return self._build_software_workflow(workflow_id)

        # 2. Try to synthesize workflow dynamically via Cognitive Engine (Model Gateway)
        try:
            from services.registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            
            # Resolve model_gateway and capability_registry services
            model_gateway = registry.get("model_gateway").metadata["gateway"]
            capability_registry = registry.get("capability_registry").metadata["registry"]
            
            # 1. Capability Discovery
            capabilities_list = capability_registry.list_capabilities()
            
            # 2. Intent & Constraint Analysis Prompt (Intermediate Plan Formulation)
            import os
            history_str = self._get_session_history(workflow_id)
            prompt = f"""You are the Realtimex cognitive planning engine.
Your task is to analyze the user's goal and generate an execution plan with steps.
You must select only from the available capabilities.

System Context:
- OS: linux
- User Home Directory: {os.path.expanduser("~")}
- Current Working Directory: {os.getcwd()}

Available Capabilities (with input requirements):
- run_command: Run a shell command. Inputs: {{"command": "<command_string>"}}. NOTE: For tasks like creating folders/directories, running terminal commands, executing scripts, etc., use this capability with appropriate shell syntax (e.g. "mkdir -p /path/to/folder").
- write_file: Write text content to a file. Inputs: {{"path": "<path>", "content": "<content>"}}
- read_file: Read text content from a file. Inputs: {{"path": "<path>"}}
- list_directory: List contents of a directory. Inputs: {{"path": "<path>"}}
- web_search: Search the web. Inputs: {{"query": "<query>"}}
- summarize_text: Summarize text. Inputs: {{"text": "<text>"}}
- generate_code: Generate programming code. Inputs: {{"prompt": "<prompt>"}}
- generate_text: Generate text response. Inputs: {{"prompt": "<prompt>"}}
- copy: Copy file/dir. Inputs: {{"source": "<source>", "destination": "<destination>"}}
- delete: Delete file/dir. Inputs: {{"path": "<path>"}}

Planning Guidelines:
1. If the user wants to generate code, design a webpage, or write a script and save it to a file path, you MUST split this into multiple steps in the plan:
   - Step 1: generate_code (or generate_text) to produce the code or content.
   - Step 2: write_file to save the generated content to the target file path.
2. To feed the output of one step into a subsequent step, use the cross-step reference string format: "Process <step_id> output" as the value of the parameter.
   Example: If step_id is "generate_code_0", write_file's input should look like: {{"path": "/home/user/Desktop/index.html", "content": "Process generate_code_0 output"}}.
{history_str}
User Goal:
"{goal}"

You must output a raw JSON dictionary with NO extra text or markdown formatting.
The dictionary MUST contain the following keys exactly:
- "intent": (string, e.g., "sys_command", "qa", "code_gen", "file_operation")
- "required_capabilities": (list of strings, selected from available capabilities in logical order)
- "step_inputs": (dictionary mapping step IDs (formatted as capability_name_index, e.g., "read_file_0") to their input dictionary containing concrete parameters computed from the user goal)
- "constraints": (dictionary with boolean keys "parallel" and "verification")
- "estimated_complexity": (string, "low", "medium", or "high")
"""

            # 3. Model Gateway Routing
            from models.provider import ModelRequest
            request = ModelRequest(
                task_id="workflow_planning",
                request_type="generate",
                capability_required="reasoning",
                prompt=prompt,
                preferred_model="llama3-70b-8192"
            )
            
            response = asyncio.run(model_gateway.generate(request))
            raw_output = response.output.strip()
            
            # Check if running under mock/simulation mode
            is_simulated = raw_output.startswith("Simulated")
            if is_simulated:
                raw_output = self._synthesize_simulated_json(goal)
                
            # Clean JSON fences if present
            if raw_output.startswith("```json"):
                raw_output = raw_output[7:]
            if raw_output.startswith("```"):
                raw_output = raw_output[3:]
            if raw_output.endswith("```"):
                raw_output = raw_output[:-3]
            raw_output = raw_output.strip()

            # Robust extraction of the JSON structure bounded by the first '{' and last '}'
            start_idx = raw_output.find("{")
            end_idx = raw_output.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw_output = raw_output[start_idx : end_idx + 1]
            
            # 4. Parse Structured Intent Analysis and Map to Step DAG
            analysis = json.loads(raw_output)
            return self._build_dag_from_analysis(workflow_id, goal, analysis, is_simulated=is_simulated)
            
        except Exception:
            # Fallback to general default workflow on parsing / gateway exceptions
            return self._build_default_workflow(workflow_id)

    def _fallback_rule_based_plan(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Fallback deterministic planner using local rules."""
        goal_lower = goal.lower()

        if "permission failure" in goal_lower:
            return self._build_permission_fail_workflow(workflow_id, goal)
        if "transient failure" in goal_lower:
            return self._build_transient_fail_workflow(workflow_id, goal)
        if "resource failure" in goal_lower:
            return self._build_resource_fail_workflow(workflow_id, goal)
        if "provider failure" in goal_lower:
            return self._build_provider_fail_workflow(workflow_id, goal)
        if "repair" in goal_lower or "permanent failure" in goal_lower:
            return self._build_repair_workflow(workflow_id, goal)
        if "parallel" in goal_lower:
            return self._build_parallel_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["retry", "recovery", "interruption", "fail"]):
            return self._build_retry_workflow(workflow_id, goal)
        if "permission" in goal_lower:
            return self._build_permission_workflow(workflow_id, goal)
        if "save" in goal_lower or "write file" in goal_lower or "write to file" in goal_lower:
            return self._build_write_file_workflow(workflow_id, goal)
        if "multi-step" in goal_lower or "read and summarize" in goal_lower:
            return self._build_multistep_workflow(workflow_id, goal)
        if "read local file" in goal_lower or "read file" in goal_lower:
            return self._build_read_file_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["python", "generate code", "coding", "function to"]):
            return self._build_generate_code_workflow(workflow_id, goal)
        if "summarize" in goal_lower or "summarization" in goal_lower:
            return self._build_summarization_workflow(workflow_id, goal)
        if "research" in goal_lower or "search" in goal_lower:
            return self._build_research_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["explain", "answer", "question", "what", "how", "recursion", "hello", "hi", "hey", "help"]):
            return self._build_answer_question_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["portfolio"]):
            return self._build_software_workflow(workflow_id)

        return self._build_default_workflow(workflow_id)

    def _get_session_history(self, workflow_id: str) -> str:
        """Retrieve previous tasks and outputs in the same session to build conversation history."""
        try:
            from services.registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            wf_mgr = registry.get("workflow_manager").metadata["manager"]
            task_mgr = registry.get("task_manager").metadata["manager"]
            
            wf = wf_mgr.load_workflow(workflow_id)
            current_task = task_mgr.get_task(wf.parent_task_id)
            session_id = current_task.metadata.get("session_id")
            
            if not session_id:
                return ""
                
            all_tasks = task_mgr._repository.find_by(
                lambda t: t.metadata.get("session_id") == session_id
            )
            all_tasks = sorted(all_tasks, key=lambda t: t.created_at)
            
            history_lines = []
            for t in all_tasks:
                if t.task_id == current_task.task_id:
                    continue
                history_lines.append(f"User: {t.goal}")
                
                try:
                    mem_mgr = registry.get("memory_manager").metadata["manager"]
                    if mem_mgr:
                        memories = mem_mgr.search(query={"owner": t.task_id, "scope": "task"})
                        if memories:
                            content = memories[0].content
                            if content.startswith("Workflow result:"):
                                content = content[len("Workflow result:"):].strip()
                            if content.startswith("[") and "]" in content:
                                content = content.split("]", 1)[1].strip()
                            history_lines.append(f"System Output: {content}")
                except Exception:
                    pass
            
            if history_lines:
                return "\nSession Conversation History:\n" + "\n".join(history_lines) + "\n"
        except Exception:
            pass
        return ""

    def _synthesize_simulated_json(self, goal: str) -> str:
        """Simulate cognitive intent analysis by translating goal to JSON."""
        goal_lower = goal.lower()
        
        if "permission failure" in goal_lower:
            analysis = {
                "intent": "permission_failure_test",
                "required_capabilities": ["summarize_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "transient failure" in goal_lower:
            analysis = {
                "intent": "transient_failure_test",
                "required_capabilities": ["summarize_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "resource failure" in goal_lower:
            analysis = {
                "intent": "resource_failure_test",
                "required_capabilities": ["summarize_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "provider failure" in goal_lower:
            analysis = {
                "intent": "provider_failure_test",
                "required_capabilities": ["summarize_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "repair" in goal_lower or "permanent failure" in goal_lower:
            analysis = {
                "intent": "plan_repair_test",
                "required_capabilities": ["summarize_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "parallel" in goal_lower:
            analysis = {
                "intent": "parallel_search",
                "required_capabilities": ["web_search", "web_search", "generate_text"],
                "constraints": {"parallel": True, "verification": False},
                "estimated_complexity": "medium"
            }
        elif any(kw in goal_lower for kw in ["retry", "recovery", "interruption", "fail"]):
            analysis = {
                "intent": "retry_test",
                "required_capabilities": ["summarize_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "permission" in goal_lower:
            analysis = {
                "intent": "permission_check",
                "required_capabilities": ["permission_check"],
                "constraints": {"parallel": False, "verification": True},
                "estimated_complexity": "low"
            }
        elif "save" in goal_lower or "write file" in goal_lower or "write to file" in goal_lower:
            analysis = {
                "intent": "file_operation",
                "required_capabilities": ["write_file"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "multi-step" in goal_lower or "read and summarize" in goal_lower:
            analysis = {
                "intent": "read_summarize_write",
                "required_capabilities": ["read_file", "summarize_text", "write_file"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "medium"
            }
        elif "read local file" in goal_lower or "read file" in goal_lower:
            analysis = {
                "intent": "file_read",
                "required_capabilities": ["read_file"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif any(kw in goal_lower for kw in ["python", "generate code", "coding", "function to"]):
            analysis = {
                "intent": "code_generation",
                "required_capabilities": ["generate_code"],
                "constraints": {"parallel": False, "verification": True},
                "estimated_complexity": "medium"
            }
        elif "summarize" in goal_lower or "summarization" in goal_lower:
            analysis = {
                "intent": "summarization",
                "required_capabilities": ["summarize_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        elif "research" in goal_lower or "search" in goal_lower:
            analysis = {
                "intent": "research",
                "required_capabilities": ["web_search", "generate_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "medium"
            }
        elif any(kw in goal_lower for kw in ["explain", "answer", "question", "what", "how", "recursion", "hello", "hi", "hey", "help"]):
            analysis = {
                "intent": "qa",
                "required_capabilities": ["generate_text"],
                "constraints": {"parallel": False, "verification": False},
                "estimated_complexity": "low"
            }
        else:
            analysis = {
                "intent": "generic_pipeline",
                "required_capabilities": ["read_file", "summarize_text", "read_file"],
                "constraints": {"parallel": False, "verification": True},
                "estimated_complexity": "medium"
            }
            
        return json.dumps(analysis)

    def _build_dag_from_analysis(self, workflow_id: str, goal: str, analysis: dict[str, Any], is_simulated: bool = False) -> list[WorkflowStep]:
        """Convert intermediate structured analysis into a step DAG."""
        intent = analysis.get("intent", "generic")
        required_caps = analysis.get("required_capabilities", [])
        constraints = analysis.get("constraints", {})
        is_parallel = constraints.get("parallel", False)
        
        steps = []
        
        # 1. Dispatching to builders based on intent & capabilities
        if intent == "permission_failure_test":
            steps = self._build_permission_fail_workflow(workflow_id, goal)
        elif intent == "transient_failure_test":
            steps = self._build_transient_fail_workflow(workflow_id, goal)
        elif intent == "resource_failure_test":
            steps = self._build_resource_fail_workflow(workflow_id, goal)
        elif intent == "provider_failure_test":
            steps = self._build_provider_fail_workflow(workflow_id, goal)
        elif intent == "plan_repair_test" or "permanent failure" in goal.lower():
            steps = self._build_repair_workflow(workflow_id, goal)
        elif intent == "parallel_search" or (is_parallel and "web_search" in required_caps):
            steps = self._build_parallel_workflow(workflow_id, goal)
        elif intent == "retry_test" or any(kw in goal.lower() for kw in ["retry", "recovery", "interruption", "fail"]):
            steps = self._build_retry_workflow(workflow_id, goal)
        elif intent == "permission_check" or "permission" in goal.lower():
            steps = self._build_permission_workflow(workflow_id, goal)
        elif any(kw in goal.lower() for kw in ["write", "code", "create", "make", "generate", "build", "refactor"]) and any(kw in goal.lower() for kw in ["python", "html", "css", "calculator", "function", "program", "script"]) and any(kw in goal.lower() for kw in ["save", "write file", "write to file"]):
            steps = self._build_code_and_save_workflow(workflow_id, goal)
        elif "save" in goal.lower() or "write file" in goal.lower() or "write to file" in goal.lower():
            steps = self._build_write_file_workflow(workflow_id, goal)
        elif is_simulated and (intent == "read_summarize_write" or ("read_file" in required_caps and "write_file" in required_caps)):
            steps = self._build_multistep_workflow(workflow_id, goal)
        elif is_simulated and (intent == "file_read" or required_caps == ["read_file"]):
            steps = self._build_read_file_workflow(workflow_id, goal)
        elif is_simulated and (intent == "code_generation" or "generate_code" in required_caps):
            steps = self._build_generate_code_workflow(workflow_id, goal)
        elif is_simulated and (intent == "summarization" or "summarize_text" in required_caps):
            steps = self._build_summarization_workflow(workflow_id, goal)
        elif is_simulated and (intent == "research" or ("web_search" in required_caps and "generate_text" in required_caps)):
            steps = self._build_research_workflow(workflow_id, goal)
        elif is_simulated and (intent == "qa" or "generate_text" in required_caps):
            steps = self._build_answer_question_workflow(workflow_id, goal)
        else:
            # Fallback default sequential DAG mapping
            prev_id = None
            step_inputs = analysis.get("step_inputs", {})
            for idx, cap in enumerate(required_caps):
                step_id = f"{cap}_{idx}"
                deps = frozenset([prev_id]) if prev_id else frozenset()
                
                # Fetch inputs generated by LLM, fallback to default prompt format if missing
                inp = step_inputs.get(step_id, step_inputs.get(cap, {}))
                if not inp:
                    inp = {"prompt": goal if idx == 0 else f"Process {prev_id} output"}
                elif "prompt" not in inp and "text" not in inp and "command" not in inp and "path" not in inp and "query" not in inp:
                    # If LLM returned empty or mismatch, overlay basic prompt
                    inp["prompt"] = goal
                
                steps.append(
                    WorkflowStep(
                        step_id=step_id,
                        workflow_id=workflow_id,
                        capability=cap,
                        input_data=inp,
                        status=StepState.PENDING,
                        dependencies=deps,
                        estimated_time=2.0,
                        estimated_cost=0.05
                    )
                )
                prev_id = step_id
                
        return steps

    def _build_permission_fail_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a workflow step designed to fail with a permission error."""
        return [
            WorkflowStep(
                step_id="perm_fail_step",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": "Hello", "step_id": "perm_fail_step", "simulate_permission_fail": True, "max_retries": 1},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01
            )
        ]

    def _build_transient_fail_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a workflow step designed to fail with a transient error (succeeds on retry)."""
        return [
            WorkflowStep(
                step_id="transient_fail_step",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": "Hello", "step_id": "transient_fail_step", "simulate_transient_fail": True, "max_retries": 2},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01
            )
        ]

    def _build_resource_fail_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a workflow step designed to fail with a resource error."""
        return [
            WorkflowStep(
                step_id="resource_fail_step",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": "Hello", "step_id": "resource_fail_step", "simulate_resource_fail": True, "max_retries": 1},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01
            )
        ]

    def _build_provider_fail_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a workflow step designed to fail with a provider error."""
        return [
            WorkflowStep(
                step_id="provider_fail_step",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": "Hello", "step_id": "provider_fail_step", "simulate_provider_fail": True, "max_retries": 1},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01
            )
        ]

    def _build_summarization_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step summarization workflow."""
        text = goal
        for prefix in ["summarize this text:", "summarize text:", "summarize:"]:
            if goal.lower().startswith(prefix):
                text = goal[len(prefix):].strip()
                break

        return [
            WorkflowStep(
                step_id="summarize",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": text},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.05,
            )
        ]

    def _build_answer_question_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step question answering workflow."""
        return [
            WorkflowStep(
                step_id="answer",
                workflow_id=workflow_id,
                capability="generate_text",
                input_data={"prompt": goal},
                status=StepState.PENDING,
                estimated_time=3.0,
                estimated_cost=0.08,
            )
        ]

    def _build_generate_code_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step code generation workflow."""
        return [
            WorkflowStep(
                step_id="code_gen",
                workflow_id=workflow_id,
                capability="generate_code",
                input_data={"prompt": goal},
                status=StepState.PENDING,
                estimated_time=4.0,
                estimated_cost=0.12,
            )
        ]

    def _build_research_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a sequential 2-step research workflow (search -> synthesize)."""
        return [
            WorkflowStep(
                step_id="search",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": goal},
                status=StepState.PENDING,
                estimated_time=3.0,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="synthesize",
                workflow_id=workflow_id,
                capability="generate_text",
                input_data={"prompt": f"Synthesize findings for: {goal}"},
                status=StepState.PENDING,
                dependencies=frozenset(["search"]),
                estimated_time=2.0,
                estimated_cost=0.04,
            )
        ]

    def _build_read_file_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step read file workflow."""
        path = "logs/test_input.txt"
        if ":" in goal:
            path = goal.split(":", 1)[1].strip()
        elif "read file" in goal.lower():
            parts = goal.lower().split("read file")
            if len(parts) > 1:
                path = parts[1].strip()
        return [
            WorkflowStep(
                step_id="read_file_step",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"file_path": path},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01,
            )
        ]

    def _build_multistep_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a sequential multi-step workflow (read -> summarize -> write)."""
        return [
            WorkflowStep(
                step_id="read",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"file_path": "logs/test_input.txt"},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01,
            ),
            WorkflowStep(
                step_id="summarize",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"prompt": "Summarize the file contents"},
                status=StepState.PENDING,
                dependencies=frozenset(["read"]),
                estimated_time=2.0,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="write",
                workflow_id=workflow_id,
                capability="write_file",
                input_data={"file_path": "logs/test_summary.txt", "content": "Summary result: successful multi-step workflow."},
                status=StepState.PENDING,
                dependencies=frozenset(["summarize"]),
                estimated_time=1.0,
                estimated_cost=0.01,
            )
        ]

    def _build_parallel_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a parallel workflow with a merge step."""
        return [
            WorkflowStep(
                step_id="search_a",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": "Topic A research"},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.04,
            ),
            WorkflowStep(
                step_id="search_b",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": "Topic B research"},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.04,
            ),
            WorkflowStep(
                step_id="merge",
                workflow_id=workflow_id,
                capability="generate_text",
                input_data={"prompt": "Synthesize results from Topic A and Topic B searches."},
                status=StepState.PENDING,
                dependencies=frozenset(["search_a", "search_b"]),
                estimated_time=3.0,
                estimated_cost=0.06,
            )
        ]

    def _build_retry_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a retry testing workflow with a step that initially fails."""
        return [
            WorkflowStep(
                step_id="unstable_step",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": "Intermittent failure test data.", "step_id": "unstable_step", "simulate_fail": True},
                status=StepState.PENDING,
                estimated_time=2.0,
                estimated_cost=0.05,
            )
        ]

    def _build_repair_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a workflow containing a step that will fail permanently to trigger plan repair."""
        return [
            WorkflowStep(
                step_id="failing_step",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text": "Fail permanently.", "step_id": "failing_step", "simulate_permanent_fail": True, "max_retries": 1},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01,
            )
        ]

    def _build_permission_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a permission verification workflow step."""
        return [
            WorkflowStep(
                step_id="perm_check",
                workflow_id=workflow_id,
                capability="permission_check",
                input_data={"check": True},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.01,
            )
        ]

    def _build_software_workflow(self, workflow_id: str) -> list[WorkflowStep]:
        """Generate a realistic 6-step software/web development workflow."""
        steps = [
            WorkflowStep(
                step_id="planning",
                workflow_id=workflow_id,
                capability="plan_task",
                input_data={"scope": "software_development"},
                status=StepState.PENDING,
                estimated_time=1.5,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="research",
                workflow_id=workflow_id,
                capability="web_search",
                input_data={"query": "best web portfolio practices"},
                status=StepState.PENDING,
                dependencies=frozenset(["planning"]),
                estimated_time=3.0,
                estimated_cost=0.10,
            ),
            WorkflowStep(
                step_id="design",
                workflow_id=workflow_id,
                capability="generate_image",
                input_data={"prompt": "modern portfolio design mockup"},
                status=StepState.PENDING,
                dependencies=frozenset(["research"]),
                estimated_time=4.0,
                estimated_cost=0.40,
            ),
            WorkflowStep(
                step_id="code",
                workflow_id=workflow_id,
                capability="write_file",
                input_data={"file_path": "portfolio/index.html"},
                status=StepState.PENDING,
                dependencies=frozenset(["design"]),
                estimated_time=6.0,
                estimated_cost=0.15,
            ),
            WorkflowStep(
                step_id="verification",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"file_path": "portfolio/index.html"},
                status=StepState.PENDING,
                dependencies=frozenset(["code"]),
                estimated_time=2.0,
                estimated_cost=0.05,
            ),
            WorkflowStep(
                step_id="packaging",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"text_source": "build_logs"},
                status=StepState.PENDING,
                dependencies=frozenset(["verification"]),
                estimated_time=1.0,
                estimated_cost=0.02,
            ),
        ]
        return steps

    def _build_default_workflow(self, workflow_id: str) -> list[WorkflowStep]:
        """Generate a general 3-step workflow (analyze, process, verify)."""
        steps = [
            WorkflowStep(
                step_id="analyze",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"target": "source_document"},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.02,
            ),
            WorkflowStep(
                step_id="process",
                workflow_id=workflow_id,
                capability="summarize_text",
                input_data={"length": "medium"},
                status=StepState.PENDING,
                dependencies=frozenset(["analyze"]),
                estimated_time=2.0,
                estimated_cost=0.08,
            ),
            WorkflowStep(
                step_id="verify",
                workflow_id=workflow_id,
                capability="read_file",
                input_data={"target": "summary_output"},
                status=StepState.PENDING,
                dependencies=frozenset(["process"]),
                estimated_time=1.0,
                estimated_cost=0.02,
            ),
        ]
        return steps

    def _resolve_target_file_path(self, workflow_id: str, goal: str) -> str:
        """Resolve the target path and filename for a file operation, supporting session history and fallback."""
        goal_lower = goal.lower()
        import os
        path = "saved_file.txt"
        session_goals = []
        try:
            from services.registry import ServiceRegistry
            registry = ServiceRegistry.get_instance()
            wf_mgr = registry.get("workflow_manager").metadata["manager"]
            task_mgr = registry.get("task_manager").metadata["manager"]
            wf = wf_mgr.load_workflow(workflow_id)
            current_task = task_mgr.get_task(wf.parent_task_id)
            session_id = current_task.metadata.get("session_id")
            if session_id:
                all_tasks = task_mgr._repository.find_by(
                    lambda t: t.metadata.get("session_id") == session_id
                )
                all_tasks = sorted(all_tasks, key=lambda t: t.created_at)
                for t in all_tasks:
                    session_goals.append(t.goal.lower())
        except Exception:
            pass
            
        combined_context_goals = " ".join(session_goals) + " " + goal.lower()
        
        if "desktop" in combined_context_goals:
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            import re
            filename_match = re.search(r'([a-zA-Z0-9_\-]+\.py|[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)', combined_context_goals)
            if filename_match:
                filename = filename_match.group(1)
            else:
                if "even" in combined_context_goals or "odd" in combined_context_goals:
                    filename = "even_odd.py"
                elif "fibonacci" in combined_context_goals:
                    filename = "fibonacci.py"
                elif "calculator" in combined_context_goals:
                    filename = "calculator.py"
                elif "login" in combined_context_goals:
                    filename = "login.html"
                else:
                    filename = "script.py"
            path = os.path.join(desktop_dir, filename)
        else:
            import re
            filename_match = re.search(r'([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+)', combined_context_goals)
            if filename_match:
                path = filename_match.group(1)
            else:
                if "even" in combined_context_goals or "odd" in combined_context_goals:
                    path = "even_odd.py"
                elif "fibonacci" in combined_context_goals:
                    path = "fibonacci.py"
                elif "calculator" in combined_context_goals:
                    path = "calculator.py"
                elif "login" in combined_context_goals:
                    path = "login.html"
                else:
                    path = "saved_file.txt"
        return path

    def _build_write_file_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a single-step write file workflow, resolving context path & contents."""
        path = self._resolve_target_file_path(workflow_id, goal)
        content_ref = "Process code_gen output"
        from workflow.step import StepState
        return [
            WorkflowStep(
                step_id="write",
                workflow_id=workflow_id,
                capability="write_file",
                input_data={"path": path, "file_path": path, "content": content_ref},
                status=StepState.PENDING,
                estimated_time=1.0,
                estimated_cost=0.02,
            )
        ]

    def _build_code_and_save_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a 2-step code generation and saving workflow."""
        path = self._resolve_target_file_path(workflow_id, goal)
        from workflow.step import StepState
        return [
            WorkflowStep(
                step_id="code_gen",
                workflow_id=workflow_id,
                capability="generate_code",
                input_data={"prompt": goal},
                status=StepState.PENDING,
                estimated_time=4.0,
                estimated_cost=0.12,
            ),
            WorkflowStep(
                step_id="write",
                workflow_id=workflow_id,
                capability="write_file",
                input_data={"path": path, "file_path": path, "content": "Process code_gen output"},
                status=StepState.PENDING,
                dependencies=frozenset(["code_gen"]),
                estimated_time=1.0,
                estimated_cost=0.02,
            )
        ]

    def _build_native_tool_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep] | None:
        goal_lower = goal.lower()
        from workflow.step import StepState
        
        # 1. Folder creation
        if any(kw in goal_lower for kw in ("create folder", "create directory", "make directory", "mkdir")):
            path = ""
            for kw in ("create folder", "create directory", "make directory", "mkdir"):
                if kw in goal_lower:
                    idx = goal_lower.index(kw)
                    path = goal[idx + len(kw):].strip()
                    break
            if path:
                path = path.strip("'\"")
                return [
                    WorkflowStep(
                        step_id="mkdir",
                        workflow_id=workflow_id,
                        capability="run_command",
                        input_data={"command": f"mkdir -p {path}"},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                    )
                ]

        # 2. File deletion
        if any(kw in goal_lower for kw in ("delete file", "remove file", "delete folder", "remove folder", "rmdir", "rm ")):
            path = ""
            for kw in ("delete file", "remove file", "delete folder", "remove folder", "rmdir", "rm"):
                if kw in goal_lower:
                    idx = goal_lower.index(kw)
                    path = goal[idx + len(kw):].strip()
                    break
            if path:
                path = path.strip("'\"")
                return [
                    WorkflowStep(
                        step_id="delete_path",
                        workflow_id=workflow_id,
                        capability="run_command",
                        input_data={"command": f"rm -rf {path}"},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                    )
                ]

        # 3. File copy
        if any(kw in goal_lower for kw in ("copy file", "copy folder", "cp ")):
            import re
            paths = re.findall(r"(?:/[a-zA-Z0-9_\-\.\~]+)+|[a-zA-Z0-9_\-\.\~]+", goal)
            filtered_paths = [p for p in paths if p.lower() not in ("copy", "file", "folder", "cp", "to")]
            if len(filtered_paths) >= 2:
                src, dest = filtered_paths[0], filtered_paths[1]
                return [
                    WorkflowStep(
                        step_id="copy_path",
                        workflow_id=workflow_id,
                        capability="run_command",
                        input_data={"command": f"cp -r {src} {dest}"},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                    )
                ]

        # 4. File move / rename
        if any(kw in goal_lower for kw in ("move file", "move folder", "rename file", "rename folder", "mv ")):
            import re
            paths = re.findall(r"(?:/[a-zA-Z0-9_\-\.\~]+)+|[a-zA-Z0-9_\-\.\~]+", goal)
            filtered_paths = [p for p in paths if p.lower() not in ("move", "rename", "file", "folder", "mv", "to")]
            if len(filtered_paths) >= 2:
                src, dest = filtered_paths[0], filtered_paths[1]
                return [
                    WorkflowStep(
                        step_id="move_path",
                        workflow_id=workflow_id,
                        capability="run_command",
                        input_data={"command": f"mv {src} {dest}"},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                    )
                ]
                
        # 5. Compound intents check (e.g. Create a login webpage or Create login.html)
        has_create_keyword = any(kw in goal_lower for kw in ["create", "write", "generate", "build", "make", "save"])
        has_file_target = any(kw in goal_lower for kw in ["page", "webpage", "website", "calculator", "script", "program", "login", ".py", ".html", ".css", ".js", ".json"])
        if has_create_keyword and has_file_target:
            return self._build_code_and_save_workflow(workflow_id, goal)
            
        return None
