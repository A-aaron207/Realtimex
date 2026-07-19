# User Manual — Installation & Setup

This guide details how to install Realtimex and configure model gateway settings on first launch.

---

## 🚀 Quick Start Setup Wizard

Realtimex comes equipped with an interactive configuration setup wizard to get your system completely configured without editing JSON manually.

To launch the wizard, run:
```bash
python3 main.py setup
```

The wizard will guide you through:
1. **Selecting your AI model provider**: Choice between Anthropic, OpenAI, OpenRouter, Gemini, or Mock (no API key required).
2. **Entering your API key**: Captures your corresponding API key (e.g. `ANTHROPIC_API_KEY`) and saves it securely to a local `.env` file in the workspace directory.
3. **Workspace Directories**: Generates folders for logs, config schemas, capabilities, active tasks, workflow definitions, and sandbox permission records.
4. **Validating System Readiness**: Runs the `doctor` diagnostics suite automatically to confirm everything is prepared.

> [!NOTE]
> If you run `python3 main.py` and no configuration file is found, Realtimex will automatically prompt you to start this Setup Wizard.

---

## ⚙️ Manual Configuration

If you prefer to configure manually, you can edit the central configuration file located at `config/config.json`. Below is the standard structure:

```json
{
  "kernel": {
    "name": "realtimex-kernel",
    "version": "1.0.0",
    "environment": "production"
  },
  "logging": {
    "level": "INFO",
    "filename": "kernel.log"
  },
  "task_system": {
    "enabled": true,
    "tasks_directory": "tasks"
  },
  "model_gateway": {
    "default_provider": "anthropic",
    "providers": {
      "anthropic": {
        "model": "claude-3-5-sonnet"
      }
    }
  }
}
```

Ensure you export the corresponding API key before launching the kernel:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```
