"""
Extensible Workflow Planner that converts user goals into execution step graphs.
"""

from __future__ import annotations

import os
import re
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
        is_code_request = any(kw in goal_lower for kw in ["write", "code", "create", "make", "generate", "build", "refactor", "develop", "design"]) and any(kw in goal_lower for kw in ["python", "html", "css", "calculator", "function", "program", "script", "ui", "interface", "webpage", "page", "website", "app", "application", "chatbot", "bot", "dashboard"])
        is_save_request = any(kw in goal_lower for kw in ["save", "write file", "write to file", "desktop", "downloads", "documents", "in folder", "to folder", "in directory", "to directory"]) or bool(re.search(r'\b[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]{1,5}\b', goal_lower))
        # "same file", "that file", "the file" → user wants to re-save a previously generated
        # result to a new location, NOT generate fresh code. Route to write_file only.
        is_redirect_request = any(kw in goal_lower for kw in ["same file", "that file", "the file", "same webpage", "that webpage", "copy it", "put it"])
        if is_redirect_request or (is_code_request and is_save_request and any(kw in goal_lower for kw in ["same", "the file", "that file"])):
            return self._build_write_file_workflow(workflow_id, goal)
        if is_code_request and is_save_request:
            return self._build_code_and_save_workflow(workflow_id, goal)
            
        if "save" in goal_lower or "write file" in goal_lower or "write to file" in goal_lower:
            return self._build_write_file_workflow(workflow_id, goal)
        if "multi-step" in goal_lower or "read and summarize" in goal_lower:
            return self._build_multistep_workflow(workflow_id, goal)
        if "read local file" in goal_lower or "read file" in goal_lower:
            return self._build_read_file_workflow(workflow_id, goal)
        # Check summarize BEFORE generic code keywords — "summarize what Python is..."
        # should route to summarization, not code generation.
        if "summarize" in goal_lower or "summarization" in goal_lower:
            return self._build_summarization_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["python", "generate code", "coding", "function to"]):
            return self._build_generate_code_workflow(workflow_id, goal)
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
3. When moving, copying, or deleting files, NEVER use shell wildcards like 'mv *', 'mv ./*', 'cp *', 'rm -rf *'. ALWAYS specify the exact, concrete filenames (e.g. 'mv index.html style.css main.js /path/to/destination').
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
        # Check compound code and save requests
        is_code = any(kw in goal_lower for kw in ["write", "code", "create", "make", "generate", "build", "refactor", "develop", "design"]) and any(kw in goal_lower for kw in ["python", "html", "css", "calculator", "function", "program", "script", "ui", "interface", "webpage", "page", "website", "app", "application", "chatbot", "bot", "dashboard"])
        is_save = any(kw in goal_lower for kw in ["save", "write file", "write to file", "desktop", "downloads", "documents", "folder", "directory"]) or bool(re.search(r'\b[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]{1,5}\b', goal_lower))
        if any(kw in goal_lower for kw in ["same file", "that file", "the file", "same webpage", "that webpage", "copy it", "put it"]):
            return self._build_write_file_workflow(workflow_id, goal)
        if is_code and is_save:
            return self._build_code_and_save_workflow(workflow_id, goal)
        if "save" in goal_lower or "write file" in goal_lower or "write to file" in goal_lower:
            return self._build_write_file_workflow(workflow_id, goal)
        if "multi-step" in goal_lower or "read and summarize" in goal_lower:
            return self._build_multistep_workflow(workflow_id, goal)
        if "read local file" in goal_lower or "read file" in goal_lower:
            return self._build_read_file_workflow(workflow_id, goal)
        # summarize must beat "python" keyword — "summarize what Python is" → summarize
        if "summarize" in goal_lower or "summarization" in goal_lower:
            return self._build_summarization_workflow(workflow_id, goal)
        if any(kw in goal_lower for kw in ["python", "generate code", "coding", "function to"]):
            return self._build_generate_code_workflow(workflow_id, goal)
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
                
                inp = step_inputs.get(step_id, step_inputs.get(cap, {}))
                if not inp:
                    inp = {"prompt": goal if idx == 0 else f"Process {prev_id} output"}
                elif "prompt" not in inp and "text" not in inp and "command" not in inp and "path" not in inp and "query" not in inp and "file_path" not in inp:
                    # If LLM returned empty or mismatch, overlay basic prompt
                    inp["prompt"] = goal
                
                # Concrete parameter binding for capabilities requiring specific inputs
                if cap == "write_file":
                    if not inp.get("file_path") and not inp.get("path") and not inp.get("target"):
                        resolved_path = self._resolve_target_file_path(workflow_id, goal)
                        inp["file_path"] = resolved_path
                        inp["path"] = resolved_path
                    if not inp.get("content"):
                        inp["content"] = f"Process {prev_id} output" if prev_id else "Process code_gen output"
                elif cap == "generate_code":
                    if not inp.get("file_path") and not inp.get("path"):
                        inp["file_path"] = self._resolve_target_file_path(workflow_id, goal)
                elif cap in ("run_command", "execute_snippet"):
                    if not inp.get("command"):
                        inp["command"] = inp.get("prompt", goal)
                
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
        import os, re
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

        # --- Step 1: Try to find an explicit filename (e.g. "index.html", "app.py") ---
        filename_match = re.search(r'\b([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]{1,5})\b', combined_context_goals)
        explicit_filename = filename_match.group(1) if filename_match else None

        # --- Step 1b: Try to find a named entity like "called Iris", "named Iris" ---
        if not explicit_filename:
            named_match = re.search(r'\b(?:called|named|title|titling)\s+([a-zA-Z0-9_\-]+)\b', combined_context_goals)
            if named_match:
                base_name = named_match.group(1).lower()
                if any(w in combined_context_goals for w in ("html", "webpage", "website", "ui", "interface", "page")):
                    explicit_filename = f"{base_name}.html"
                elif any(w in combined_context_goals for w in ("python", "script", "program")):
                    explicit_filename = f"{base_name}.py"
                elif "css" in combined_context_goals:
                    explicit_filename = f"{base_name}.css"
                elif any(w in combined_context_goals for w in ("js", "javascript")):
                    explicit_filename = f"{base_name}.js"
                else:
                    explicit_filename = f"{base_name}.txt"

        # --- Step 2: Infer from content-type keywords if no explicit name ---
        def _infer_filename(ctx: str) -> str:
            if "html" in ctx or "webpage" in ctx or "web page" in ctx or "website" in ctx or "ui" in ctx or "interface" in ctx or "landing" in ctx or "page" in ctx:
                return "index.html"
            if "css" in ctx or "stylesheet" in ctx:
                return "style.css"
            if "javascript" in ctx or " js " in ctx:
                return "script.js"
            if "even" in ctx or "odd" in ctx:
                return "even_odd.py"
            if "fibonacci" in ctx:
                return "fibonacci.py"
            if "calculator" in ctx:
                return "calculator.py"
            if "login" in ctx:
                return "login.html"
            return "saved_file.txt"

        if "desktop" in combined_context_goals:
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            filename = explicit_filename or _infer_filename(combined_context_goals)
            path = os.path.join(desktop_dir, filename)
        else:
            if explicit_filename:
                path = explicit_filename
            else:
                path = _infer_filename(combined_context_goals)
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

    def _get_session_generated_files(self, workflow_id: str) -> list[str]:
        """Find recently generated files from this session or workspace to move/copy."""
        found_files: list[str] = []
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
                all_tasks = sorted(all_tasks, key=lambda t: t.created_at, reverse=True)
                for t in all_tasks:
                    matches = re.findall(r'\b([a-zA-Z0-9_\-]+\.[a-zA-Z0-9]{1,5})\b', t.goal)
                    for m in matches:
                        if m not in found_files and os.path.exists(m):
                            found_files.append(m)
        except Exception:
            pass

        # If none found from session goals, check common generated files in CWD
        if not found_files:
            common = ["index.html", "style.css", "main.js", "script.js", "Index.html", "Style.css", "iris.html", "saved_file.txt"]
            found_files = [f for f in common if os.path.exists(f)]

        return found_files

    def _build_code_and_save_workflow(self, workflow_id: str, goal: str) -> list[WorkflowStep]:
        """Generate a code generation and saving workflow, supporting single and multiple files."""
        # Check if the goal specifies multiple concrete filenames (e.g. Index.html, Style.css, main.js)
        raw_filenames = re.findall(r'\b([a-zA-Z0-9_\-]+\.(?:html|css|js|ts|py|json|txt))\b', goal, re.IGNORECASE)
        filenames: list[str] = []
        for f in raw_filenames:
            if f.lower() not in [x.lower() for x in filenames]:
                filenames.append(f)

        from workflow.step import StepState
        if len(filenames) > 1:
            goal_lower = goal.lower()
            target_dir = ""
            if "desktop" in goal_lower:
                target_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            elif "downloads" in goal_lower:
                target_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            elif "documents" in goal_lower:
                target_dir = os.path.join(os.path.expanduser("~"), "Documents")

            steps = []
            for idx, fname in enumerate(filenames):
                file_path = os.path.join(target_dir, fname) if target_dir else fname
                code_step_id = f"code_gen_{idx}"
                write_step_id = f"write_{idx}"
                
                ext = os.path.splitext(fname)[1].lower()
                if ext in (".html", ".htm"):
                    file_prompt = f"Create the HTML document {fname} for the web project. Link to stylesheet and scripts properly. Goal: {goal}"
                elif ext == ".css":
                    file_prompt = f"Create the CSS stylesheet {fname} matching the design. Goal: {goal}"
                elif ext in (".js", ".ts"):
                    file_prompt = f"Create the JavaScript code {fname} for the interactive elements. Goal: {goal}"
                else:
                    file_prompt = f"Create the code for {fname}. Goal: {goal}"

                steps.append(
                    WorkflowStep(
                        step_id=code_step_id,
                        workflow_id=workflow_id,
                        capability="generate_code",
                        input_data={"prompt": file_prompt, "file_path": file_path},
                        status=StepState.PENDING,
                        estimated_time=3.0,
                        estimated_cost=0.08,
                    )
                )
                steps.append(
                    WorkflowStep(
                        step_id=write_step_id,
                        workflow_id=workflow_id,
                        capability="write_file",
                        input_data={"path": file_path, "file_path": file_path, "content": f"Process {code_step_id} output"},
                        status=StepState.PENDING,
                        dependencies=frozenset([code_step_id]),
                        estimated_time=1.0,
                        estimated_cost=0.02,
                    )
                )
            return steps

        path = self._resolve_target_file_path(workflow_id, goal)
        return [
            WorkflowStep(
                step_id="code_gen",
                workflow_id=workflow_id,
                capability="generate_code",
                input_data={"prompt": goal, "file_path": path},
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

    def _extract_path_from_goal(self, goal: str, goal_lower: str) -> str:
        """
        Extract a file/directory path from a natural language goal string.
        
        Handles patterns like:
        - "delete all contents from my Desktop folder"
        - "empty the ~/Downloads directory"
        - "clear /home/user/temp"
        - "remove all files from Documents"
        """
        import os
        import re
        
        # 1. Try to find a ~ path first (e.g. ~/Desktop) — before absolute paths
        #    because ~/Downloads would otherwise match the absolute regex as /Downloads
        tilde_match = re.search(r'(~/[a-zA-Z0-9_\-\./]+)', goal)
        if tilde_match:
            return os.path.expanduser(tilde_match.group(1))
        
        # 2. Try to find an explicit absolute path (e.g. /home/aarons/Desktop)
        abs_match = re.search(r'(/(?:[a-zA-Z0-9_\-\.~]+/)*[a-zA-Z0-9_\-\.~]+)', goal)
        if abs_match:
            return abs_match.group(1)
        
        # 3. Map common named directories from natural language
        home_dir = os.path.expanduser("~")
        named_dirs = {
            "desktop": os.path.join(home_dir, "Desktop"),
            "downloads": os.path.join(home_dir, "Downloads"),
            "documents": os.path.join(home_dir, "Documents"),
            "pictures": os.path.join(home_dir, "Pictures"),
            "videos": os.path.join(home_dir, "Videos"),
            "music": os.path.join(home_dir, "Music"),
            "templates": os.path.join(home_dir, "Templates"),
            "public": os.path.join(home_dir, "Public"),
            "home": home_dir,
            "temp": "/tmp",
            "tmp": "/tmp",
        }
        
        for name, path in named_dirs.items():
            # Match "desktop folder", "my desktop", "the desktop directory", etc.
            if re.search(rf'\b{name}\b', goal_lower):
                return path
        
        # 4. Try to extract path after common prepositions (from, in, at, of)
        prep_match = re.search(r'(?:from|in|at|of)\s+([a-zA-Z0-9_\-\./~]+(?:/[a-zA-Z0-9_\-\.]+)*)', goal)
        if prep_match:
            candidate = prep_match.group(1)
            if candidate and candidate not in ("my", "the", "a", "all", "folder", "directory", "file"):
                return os.path.expanduser(candidate)
        
        # 5. Fallback: try to extract path after deletion keywords
        for kw in ("delete file", "remove file", "delete folder", "remove folder", "rmdir", "rm"):
            if kw in goal_lower:
                idx = goal_lower.index(kw)
                remainder = goal[idx + len(kw):].strip()
                if remainder:
                    return remainder.split()[0]
        
        return ""

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

        # 2. File/folder deletion (including "delete all contents from folder" patterns)
        deletion_keywords_exact = ("delete file", "remove file", "delete folder", "remove folder", "rmdir", "rm ")
        deletion_keywords_broad = ("delete all", "delete the contents", "delete contents", "remove all",
                                   "remove the contents", "remove contents", "erase all", "erase contents",
                                   "delete everything")
        # Also detect combinations: action word + target word even when separated
        # e.g. "empty the Downloads folder", "clear my temp directory", "wipe the desktop"
        deletion_action_words = ("empty", "clear", "clean", "wipe", "purge")
        deletion_target_words = ("folder", "directory", "dir", "desktop", "downloads", "documents",
                                 "pictures", "videos", "music", "templates", "public", "temp", "tmp")
        has_deletion_combo = (any(w in goal_lower for w in deletion_action_words)
                              and any(w in goal_lower for w in deletion_target_words))
        is_deletion_request = any(kw in goal_lower for kw in deletion_keywords_exact + deletion_keywords_broad) or has_deletion_combo
        if is_deletion_request:
            path = self._extract_path_from_goal(goal, goal_lower)
            if path:
                path = path.strip("'\"")
                # If the goal indicates clearing CONTENTS of a folder (not deleting the folder itself),
                # use find -mindepth 1 -delete to safely remove all contents without removing the parent dir
                is_contents_deletion = any(kw in goal_lower for kw in (
                    "contents", "all the contents", "everything in", "everything from",
                    "all files", "all the files", "files from", "files in",
                    "delete all", "remove all", "clear", "empty", "clean", "wipe", "erase all"
                ))
                # Resolve ~ and common named directories
                resolved_path = os.path.expanduser(path)
                if is_contents_deletion and os.path.isdir(resolved_path):
                    # Safely delete directory contents without removing the directory itself
                    cmd = f"find {resolved_path} -mindepth 1 -maxdepth 1 -exec rm -rf {{}} +"
                else:
                    cmd = f"rm -rf {resolved_path}"
                return [
                    WorkflowStep(
                        step_id="delete_path",
                        workflow_id=workflow_id,
                        capability="run_command",
                        input_data={"command": cmd},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                    )
                ]

        # 3. File move / copy / rename (including conversational "move those files to desktop", "copy them to ...")
        is_move_goal = any(kw in goal_lower for kw in ("move", "mv ", "rename"))
        is_copy_goal = any(kw in goal_lower for kw in ("copy", "cp "))
        if is_move_goal or is_copy_goal:
            op_cmd = "mv" if is_move_goal else "cp -r"
            dest = self._extract_path_from_goal(goal, goal_lower)
            is_conversational = any(kw in goal_lower for kw in ("those files", "the files", "these files", "them", "those", "these", "files"))
            
            # Case A: Conversational reference to session files (e.g. "move those files to my desktop")
            if is_conversational and dest:
                session_files = self._get_session_generated_files(workflow_id)
                existing_files = [f for f in session_files if os.path.exists(f)]
                target_files = existing_files if existing_files else session_files
                if not target_files:
                    target_files = [f for f in ("Index.html", "Style.css", "main.js", "index.html", "style.css", "script.js") if os.path.exists(f)]
                if not target_files:
                    target_files = ["index.html", "style.css", "main.js"]
                cmd = f"{op_cmd} {' '.join(target_files)} {dest}/"
                return [
                    WorkflowStep(
                        step_id="move_session_files" if is_move_goal else "copy_session_files",
                        workflow_id=workflow_id,
                        capability="run_command",
                        input_data={"command": cmd},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                    )
                ]

            # Case B: Explicit source and destination paths in the goal
            paths = re.findall(r"(?:/[a-zA-Z0-9_\-\.\~]+)+|[a-zA-Z0-9_\-\.\~]+", goal)
            filtered_paths = [p for p in paths if p.lower() not in ("move", "rename", "file", "folder", "mv", "cp", "copy", "to", "now", "those", "these", "the", "in", "into")]
            if dest and len(filtered_paths) >= 1:
                src_candidates = [p for p in filtered_paths if p.lower() not in ("desktop", "downloads", "documents") and (os.path.exists(p) or "." in p)]
                if src_candidates:
                    cmd = f"{op_cmd} {' '.join(src_candidates)} {dest}/"
                    return [
                        WorkflowStep(
                            step_id="move_path" if is_move_goal else "copy_path",
                            workflow_id=workflow_id,
                            capability="run_command",
                            input_data={"command": cmd},
                            status=StepState.PENDING,
                            estimated_time=1.0,
                        )
                    ]
            elif len(filtered_paths) >= 2:
                src, dst = filtered_paths[0], filtered_paths[1]
                cmd = f"{op_cmd} {src} {dst}"
                return [
                    WorkflowStep(
                        step_id="move_path" if is_move_goal else "copy_path",
                        workflow_id=workflow_id,
                        capability="run_command",
                        input_data={"command": cmd},
                        status=StepState.PENDING,
                        estimated_time=1.0,
                    )
                ]
                
        # 5. Compound intents check (e.g. Create a login webpage, Create UI Called Iris in desktop, etc.)
        has_create_keyword = any(kw in goal_lower for kw in ["create", "write", "generate", "build", "make", "save", "develop", "design", "code", "called", "named"])
        has_destination = any(kw in goal_lower for kw in ["desktop", "downloads", "documents", "in folder", "to folder", "in directory", "to directory", "in ~", "to ~", "in /", "to /"])
        has_file_target = any(kw in goal_lower for kw in [
            "page", "webpage", "website", "calculator", "script", "program", "login",
            ".py", ".html", ".css", ".js", ".json", "html", "css",
            "ui", "interface", "app", "application", "chatbot", "bot", "dashboard"
        ])
        if (has_create_keyword and has_file_target) or (has_file_target and has_destination):
            return self._build_code_and_save_workflow(workflow_id, goal)
            
        return None
