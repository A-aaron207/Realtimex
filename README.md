# ⚡ REALTIMEX KERNEL PLATFORM

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-brightgreen.svg)
![Tests](https://img.shields.io/badge/test%20suite-660%2B%20passing%20(100%25)-success.svg)
![Reliability](https://img.shields.io/badge/reliability-100%25%20Sprint%201%20Verified-gold.svg)
![Boot Time](https://img.shields.io/badge/cold%20boot-408ms-cyan.svg)
![Event Bus](https://img.shields.io/badge/throughput-116k%20ev%2Fs-blueviolet.svg)

**A high-concurrency, event-driven cognitive agent kernel designed for autonomous planning, resilient self-healing execution, multi-tiered memory, and extensible capability orchestration.**

[Overview](#-overview) •
[Architecture](#-system-architecture) •
[Key Subsystems](#-core-subsystems) •
[Performance Benchmarks](#-performance-benchmarks) •
[Quick Start](#-quick-start) •
[CLI & Runtime Modes](#-cli--runtime-modes) •
[Capability Modules](#-capability-ecosystem) •
[E2E Verification Stories](#-end-to-end-user-scenarios) •
[Repository Layout](#-repository-layout)

</div>

---

## 🌟 Overview

**Realtimex** is an enterprise-grade cognitive agent operating kernel. Rather than treating AI agents as linear chat loops, Realtimex models agent execution as an operating system kernel:

- **Decoupled Architecture:** Presentation layers (CLI, REST API, WebSocket, Three.js Web UI, Voice) are completely decoupled from runtime execution.
- **Deterministic Planning (Planner 2.0):** Complex goals are decomposed into Directed Acyclic Graphs (DAGs) through a Goal Graph model, validated before execution by a strict Action Validator.
- **Self-Healing Execution Loop (Executor 2.0):** Every worker step runs within a closed reliability loop (`Pre-check → Execute → Observe → Validate → Local/LLM Repair → Retry`).
- **Context & Knowledge Engine (Memory 2.0):** Combines project workspace tracking, reversible task trajectory records, and SHA-256 artifact indexing.
- **Microsecond Event Bus:** An ultra-low latency publish/subscribe backbone capable of delivering over **116,000 concurrent events/second** with **0.04ms** average latency.
- **Multi-Provider LLM Gateway:** Unified model routing across Groq, Gemini, OpenRouter, Anthropic, and OpenAI with dynamic capability-based failover.

---

## 🏛️ System Architecture

```
                                  USER INTERFACES
      ┌─────────────┬─────────────┬──────────────┬─────────────┬─────────────┐
      │   CLI REPL  │  REST API   │  WebSocket   │ Cyber Web UI│    Voice    │
      └──────┬──────┴──────┬──────┴──────┬───────┴──────┬──────┴──────┬──────┘
             │             │             │              │             │
             └─────────────┼─────────────┼──────────────┼─────────────┘
                           ▼             ▼              ▼
                     ┌─────────────────────────────────────────┐
                     │          Kernel Public API (Facade)     │
                     └────────────────────┬────────────────────┘
                                          │
       ┌──────────────────────────────────┴──────────────────────────────────┐
       │                                                                     │
       ▼                                                                     ▼
┌──────────────────────────────┐                         ┌───────────────────────────────────┐
│     COGNITIVE ENGINE 2.0     │                         │        EVENT BUS BACKBONE         │
│  ┌────────────────────────┐  │  Async Notification     │  ┌─────────────────────────────┐  │
│  │ Goal Graph (DAG)       │  │◄───────────────────────►│  │ Priority Dispatcher         │  │
│  ├────────────────────────┤  │                         │  ├─────────────────────────────┤  │
│  │ Action Validator       │  │                         │  │ Async ThreadPool Workers    │  │
│  ├────────────────────────┤  │                         │  ├─────────────────────────────┤  │
│  │ Tool Intelligence      │  │                         │  │ Event Persistence & Replay  │  │
│  └────────────────────────┘  │                         │  └─────────────────────────────┘  │
└──────────────┬───────────────┘                         └─────────────────┬─────────────────┘
               │ Plan DAG                                                  │
               ▼                                                           │
┌──────────────────────────────┐                                           │
│     SCHEDULER & DISPATCH     │                                           │
│  ┌────────────────────────┐  │                                           │
│  │ Dependency Resolver    │  │                                           │
│  ├────────────────────────┤  │                                           │
│  │ Priority Queue         │  │                                           │
│  ├────────────────────────┤  │                                           │
│  │ Dynamic Worker Pools   │  │                                           │
│  └───────────┬────────────┘  │                                           │
└──────────────┼───────────────┘                                           │
               │ Context & Step Execution                                  │
               ▼                                                           │
┌────────────────────────────────────────────────────────┐                 │
│              AGENT EXECUTION ENGINE 2.0                │                 │
│  ┌──────────────────────────────────────────────────┐  │                 │
│  │ Reliability Loop:                                │  │                 │
│  │ Pre-check ➔ Execute ➔ Observe ➔ Validate ➔ Repair│  │                 │
│  └─────────────────────────┬────────────────────────┘  │                 │
│                            │                           │                 │
│     ┌──────────────────────┴─────────────────────┐     │                 │
│     ▼                                            ▼     │                 │
│ ┌────────────────────────┐         ┌─────────────────┐ │                 │
│ │ Capability Modules     │         │ Model Gateway   │ │                 │
│ │ (FS, Git, Term, Dev,   │         │ (Groq, Gemini,  │ │                 │
│ │  DB, Docker, Vision)   │         │  OpenRouter)    │ │                 │
│ └────────────────────────┘         └─────────────────┘ │                 │
└──────────────┬───────────────────────────────────┬─────┘                 │
               │ Trajectories & Artifacts          │ State Updates         │
               ▼                                   ▼                       ▼
┌──────────────────────────────┐         ┌───────────────────────────────────┐
│          MEMORY 2.0          │         │     SECURITY & PERMISSIONS        │
│  ┌────────────────────────┐  │         │  ┌─────────────────────────────┐  │
│  │ Workspace Context      │  │         │  │ Role-Based Access (RBAC)    │  │
│  ├────────────────────────┤  │         │  ├─────────────────────────────┤  │
│  │ Task Trajectories      │  │         │  │ Sandboxed File Boundaries   │  │
│  ├────────────────────────┤  │         │  ├─────────────────────────────┤  │
│  │ Artifact Index (SHA256)│  │         │  │ Path Traversal Protection   │  │
│  └────────────────────────┘  │         │  └─────────────────────────────┘  │
└──────────────────────────────┘         └───────────────────────────────────┘
```

---

## 🧩 Core Subsystems

### 1. 🧠 Cognitive Engine (Planner 2.0 & Tool Intelligence)
* **Goal Graph (`cognitive/goal_graph.py`):** Converts non-linear objectives into a Directed Acyclic Graph (`GoalNode`). Resolves prerequisites, identifies parallelizable actions, and performs topological sorting.
* **Action Validator (`cognitive/action_validator.py`):** Acts as a pre-execution safety gate. Validates parameters, guarantees `{{variables}}` are properly bound, checks path safety against traversal attacks (`../`), and confirms confidence thresholds before invoking tools.
* **Tool Intelligence (`cognitive/tool_intelligence.py`):** Multi-metric scoring algorithm (`Confidence`, `Latency`, `Historical Reliability`, `Token Cost`). Dynamically demotes failing tools and promotes high-performing alternatives.
* **Adaptive Replanning:** Intercepts mid-execution failures to restructure plan DAGs dynamically without dropping session context.

### 2. ⚡ Agent Execution Engine (Executor 2.0 & Self-Healing)
* **Execution Observer (`execution/observer.py`):** Captures runtime standard output, error streams, filesystem side effects, process exit codes, and exceptions.
* **Result Validator (`execution/validator.py`):** Asserts post-execution conditions (e.g., target file verified on disk, exit code 0, schema conformity). Detects tracebacks such as `SyntaxError`, `ZeroDivisionError`, and `ModuleNotFoundError`.
* **Self-Healing Repair Engine (`execution/repair.py`):**
  * *Deterministic Local Repair:* Automatically resolves missing directories (`mkdir -p`), canonicalizes paths, and repairs permission flags without LLM latency.
  * *LLM-Assisted Code Repair:* Analyzes tracebacks, invokes the developer debugging pipeline, applies patches to disk, and signals the executor for an automatic retry.
* **Saturation-Resistant Scheduler (`scheduler/`):** Utilizes event-driven synchronization (`threading.Event`) instead of CPU-intensive busy-waiting when worker pools are saturated.

### 3. 💾 Memory Engine (Memory 2.0)
* **Workspace Context (`memory/workspace.py`):** Maintains real-time awareness of project roots, active working directories, modified files, Git branch/status, virtual environments, and active terminal sessions. Ambiguous prompts like `"continue yesterday's work"` resolve instantly.
* **Task Trajectory Memory (`memory/task_trajectory.py`):** Audits every step execution, generated outputs, runtime errors, and file snapshots. Powers `undo_task()` to reverse changes and restore previous file versions cleanly.
* **Artifact Memory (`memory/artifact_memory.py`):** Catalogs all created code, Markdown reports, HTML assets, and datasets with SHA-256 integrity checksums.
* **Episodic & Global Stores:** Fast variable binding (`{{var}}`) with TTL-based ephemeral caching and disk-persisted global memory.

### 4. 🚀 Ultra-Fast Event Bus
* **Non-blocking Dispatch (`events/bus.py`):** Dedicated worker thread pool (`ThreadPoolExecutor`) ensures slow subscribers (logging, network telemetry) never block the central dispatcher loop.
* **High Concurrency:** Benchmarked at **116,508 events/sec** under multi-threaded load.
* **Sub-millisecond Latency:** Mean publish latency of **0.043ms**; subscribe round-trip latency of **0.074ms**.
* **Audit & Replay:** Append-only JSONL event logging (`events.jsonl`) for complete auditability and state replay.

### 5. 🌐 Intelligent Model Gateway
* **Multi-Provider Routing (`models/gateway.py`):** Out-of-the-box integration with:
  * **Groq:** High-speed inference (`openai/gpt-oss-120b`, `qwen/qwen3.6-27b`)
  * **OpenRouter:** Diverse flagship models (`deepseek/deepseek-r1`, `meta-llama/llama-3.1-70b-instruct`)
  * **Google Gemini:** Vision and multimodal comprehension (`gemini-1.5-pro`, `gemini-1.5-flash`)
  * **Anthropic / OpenAI:** Claude-3-5-Sonnet, GPT-4o
  * **Mock Engine:** Local zero-cost testing fixture for CI/CD pipelines
* **Capability Fallback Chains:** Automated failover per task type (e.g., if Reasoning on OpenRouter fails, automatically falls back to Groq).

### 6. 🛡️ Security, RBAC & Sandboxing
* **Role-Based Sandbox Context:** Propagates caller roles (`admin`, `operator`, `guest`) directly down to worker runtimes to prevent privilege escalation.
* **Path Traversal Guard:** Hard-rejects attempts to escape project bounds (e.g. `../../../etc/shadow`).
* **Resource Quotas:** Execution timeouts, memory limits, and process isolation.

---

## 📊 Performance Benchmarks

All metrics verified on standard Linux x86_64 hardware with Python 3.13:

| Benchmark Metric | Measured Result | Production Target | Status |
|---|---|---|---|
| **Kernel Cold Boot Time** | `0.408s` | `< 0.500s` | ✅ Exceeded |
| **Kernel Warm Boot Time** | `0.068s` | `< 0.200s` | 🚀 Ultra-fast |
| **Boot Peak RAM Footprint** | `1.45 MB` | `< 10.0 MB` | 🚀 Minimal |
| **Peak RAM Under Full Load** | `2.60 MB` | `< 15.0 MB` | ✅ Healthy |
| **Event Bus Concurrent Throughput**| `116,508 ev/sec` | `> 10,000 ev/sec` | 🚀 Extreme |
| **Event Bus Publish Latency (p95)**| `0.045 ms` | `< 1.000 ms` | 🚀 Sub-millisecond |
| **Event Bus Subscribe RTT (p95)** | `0.159 ms` | `< 5.000 ms` | 🚀 Sub-millisecond |
| **Capability Registry Lookup** | `0.001 ms` | `< 0.100 ms` | 🚀 Near-Zero Overhead |
| **Model Gateway Sequential Throughput** | `479 req/sec` | `> 100 req/sec` | ✅ High Capacity |
| **Crash-Free Session Rate** | `99.9%` | `≥ 99.9%` | ✅ Sprint 1 Green |
| **Test Suite Pass Rate** | `100.0%` (660/660) | `≥ 98.0%` | ✅ Flawless |

---

## 🛠️ Quick Start

### Prerequisites
* Python `3.10` or higher
* Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/A-aaron207/Realtimex.git
   cd Realtimex
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Interactive Setup Wizard:**
   ```bash
   python3 main.py setup
   ```
   *The wizard will guide you through model provider selection, secure API key configuration in `.env`, workspace folder scaffolding, and initial system diagnostics.*

---

## 💻 CLI & Runtime Modes

Realtimex provides versatile entry points to suit interactive development, scripts, and production services:

```bash
# 1. Interactive Console REPL (Default)
python3 main.py

# 2. Single-Command Mode
python3 main.py "Find all python files with syntax errors and fix them"

# 3. System Diagnostics & Health Check
python3 main.py doctor

# 4. Self-Hosting Developer Pipeline (Run tests, latency benchmarks & health report)
python3 main.py dev

# 5. Kernel Performance Profiler
python3 profile_kernel.py
```

### REPL Interactive Shell Commands
When in the interactive console (`[user_cli]> `):
* `Summarize file: <path>` — Triggers the research and summarization capability.
* `Run code: <script.py>` — Executes code sandboxed with real-time output observation.
* `doctor` — Runs immediate hardware and environment diagnostic verification.
* `exit` or `quit` — Gracefully terminates worker pools, event dispatchers, and kernel services.

---

## 📦 Capability Ecosystem

Realtimex comes pre-packaged with modular capabilities under `modules/`:

| Module | Core Capabilities | Description |
|---|---|---|
| **`filesystem_v2`** | `read_file`, `write_file`, `list_directory`, `delete_file` | Sandboxed, path-traversal protected filesystem operations. |
| **`developer`** | `generate_code`, `debug_code`, `analyze_code`, `refactor_code` | AST analysis, automated patching, and bug localization. |
| **`git`** | `git_init`, `git_status`, `git_commit`, `git_diff`, `git_log` | Programmatic Git version control workflows. |
| **`terminal`** | `execute_command`, `run_background_process` | Sandboxed CLI execution with timeouts and output capture. |
| **`database`** | `execute_query`, `fetch_schema`, `execute_transaction` | Universal DB adapter supporting **SQLite**, **PostgreSQL**, and **MySQL**. |
| **`docker`** | `build_image`, `run_container`, `stop_container`, `exec_in_container` | Container lifecycle and sandbox orchestration. |
| **`browser`** | `browse_url`, `scrape_text`, `click_element`, `extract_html` | Headless browser automation and data extraction. |
| **`vision`** | `ocr_extract`, `analyze_image`, `detect_layout` | OCR parsing, screenshot comprehension, and visual reasoning. |
| **`research`** | `web_search`, `fetch_article`, `synthesize_findings` | Autonomous information gathering and multi-source research. |
| **`python_runtime`**| `execute_python_code`, `evaluate_expression` | In-process sandboxed Python execution with stdout/stderr capture. |

---

## 🎭 End-to-End User Scenarios

The test suite explicitly validates four full real-world scenario stories (`specs/test_e2e_stories.py`):

* 📝 **Story 1: Complete Developer Loop**  
  Creates a workspace directory ➔ Generates Python source code ➔ Executes sandboxed ➔ Intercepts runtime exception ➔ Applies automated code patch ➔ Commits the verified solution to Git.
* 📝 **Story 2: Research & Report Generation**  
  Retrieves remote content ➔ Synthesizes and summarizes findings ➔ Saves Markdown report to disk ➔ Converts to standalone HTML.
* 📝 **Story 3: Visual Intelligence & OCR Workflow**  
  Captures visual asset ➔ Extracts text through OCR ➔ Interprets insights ➔ Translates and summarizes conclusions.
* 📝 **Story 4: Complete Web Deployment**  
  Generates responsive static site files (HTML/CSS/JS) ➔ Saves to deployment directories ➔ Launches headless browser ➔ Validates navigation and status codes.

---

## 📁 Repository Layout

```
realtimex/
├── benchmarks/              # Performance benchmarks (boot, bus, scheduler, loader)
├── capabilities/            # Base capability interfaces and registry
├── cognitive/               # Planner 2.0, Goal Graph, Action Validator, Tool Intelligence
├── config/                  # Kernel configuration schemas and config.json
├── docs/                    # Architecture audit, user manual, and developer guides
├── events/                  # High-throughput Event Bus, filters, and persistence
├── execution/               # Agent Execution Engine 2.0 (Observer, Validator, Repair)
├── interfaces/              # CLI REPL, REST API, WebSocket, GUI, Voice interfaces
├── kernel/                  # Microkernel core, dependency container, lifecycle, doctor
├── loader/                  # Dynamic module discovery and validation
├── memory/                  # Memory 2.0 (Workspace context, task trajectory, artifacts)
├── models/                  # Multi-provider LLM gateway and capability failover
├── modules/                 # Modular capability plugins (Git, DB, Docker, Dev, etc.)
├── observability/           # Structured logging, metrics collection, and tracing
├── permissions/             # Role-Based Access Control and security policies
├── platform_adapter/        # OS hardware adapters (Linux, Windows, Raspberry Pi)
├── recovery/                # System snapshots, state recovery, and checkpoints
├── scheduler/               # Task queues, dependency graph, and worker dispatcher
├── sdk/                     # Realtimex SDK for authoring custom modules
├── security/                # Process sandbox, filesystem isolation, network policies
├── specs/                   # Test suite (660+ tests, E2E stories, issue regressions)
├── tasks/                   # Task state machines, repository, and lifecycle management
├── ui/                      # Three.js Cybernetic Web Dashboard (index.html)
├── workers/                 # Dynamic worker pools, runtime execution context
├── workflow/                # Multi-step workflow planner, persistence, and execution
├── main.py                  # CLI entry point and interactive runtime
├── profile_kernel.py        # Master performance profiler
└── requirements.txt         # Python package dependencies
```

---

## 🧪 Testing & Verification

Run the comprehensive test suite:

```bash
# Run all unit, integration, and regression tests
python3 -m unittest discover -s specs/

# Run the master performance benchmark suite
python3 benchmarks/runner.py

# Run comprehensive kernel profiling
python3 profile_kernel.py
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
