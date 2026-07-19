# User Manual — CLI Usage & Interactive REPL

This guide covers all runtime interface modes available in Realtimex.

---

## 🚀 CLI Interface Modes

Realtimex supports three runtime behaviors from the CLI:

### 1. Interactive REPL Loop (Default)
Running `python3 main.py` without arguments enters the interactive console REPL. 

```bash
python3 main.py
```
* **Prompt**: `[user_cli]> `
* **Commands**: Type your query or request (e.g. `Summarize file: logs/test.log`).
* **Exit**: Type `exit` or `quit` to cleanly exit the REPL and shut down all background schedulers.
* **Console Cleanliness**: Standard logger event logs are automatically muted in this mode and outputted directly to `logs/kernel.log` so you can focus entirely on the command prompt.

### 2. Single-Command Mode
Execute a single instruction and immediately exit:
```bash
python3 main.py "Summarize this text: Hello World!"
```

### 3. Diagnostics & Health (`doctor` mode)
Verify python compile state, directory read/write permissions, available disk space, module discovery counts, and model api environment keys:
```bash
python3 main.py doctor
```

### 4. Developer Pipeline (`dev` mode)
Run self-hosting validations (runs the pytest suite, benchmarks concurrent startup latency, reads git porcelain updates, and generates a formatted health report):
```bash
python3 main.py dev
```

---

## 🏥 Crash Reporting & Diagnostic Bundles

If the Kernel crashes during the boot sequence or encounters an unhandled exception:
1. It automatically isolates the stack trace and collects host hardware metrics.
2. It generates a diagnostics bundle JSON file inside your logs directory:
   `logs/realtimex_diagnostics_bundle_<timestamp>.json`
3. Attach this file when submitting bugs or filing issue reports.
