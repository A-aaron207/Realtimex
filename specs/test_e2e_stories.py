"""
Real-World User Scenario Tests (End-to-End Stories 1 - 4)
==========================================================
Verifies the complete execution of the 4 Real-World E2E Stories from GEMINI.md:
  1. Complete Developer Loop (Create workspace -> Generate code -> Execute sandboxed -> Debug & Fix -> Git commit)
  2. Research & Report Generation (Retrieve content -> Summarize text -> Save Markdown -> Convert to HTML)
  3. Visual Intelligence & OCR Workflow (Capture asset -> Run OCR -> Analyze/Interpret -> Summarize insights)
  4. Complete Web Deployment (Generate HTML/CSS/JS -> Save to hosting dir -> Browser navigate -> Validate load)
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kernel.api import KernelAPI
from models.provider import ModelResponse
from workers.context import ExecutionContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
LOG_DIRECTORY = PROJECT_ROOT / "logs"
MODULES_ROOT = PROJECT_ROOT / "modules"


@pytest.fixture(scope="module")
def booted_api():
    """Booted KernelAPI fixture with all standard modules loaded."""
    api = KernelAPI(
        config_path=CONFIG_PATH,
        log_directory=LOG_DIRECTORY,
        modules_root=MODULES_ROOT,
    )
    api.boot()
    yield api
    api.shutdown()


@pytest.fixture(scope="module")
def modules(booted_api):
    """Dictionary of loaded module instances."""
    loader = booted_api._kernel._boot_result.module_loader
    return {mod_id: lm.instance for mod_id, lm in loader._loaded_modules.items()}


def _mock_model_response(output: str) -> ModelResponse:
    """Helper creating a valid ModelResponse object."""
    return ModelResponse(
        output=output,
        provider_used="mock_provider",
        model_used="mock_model",
        token_usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        latency=0.01,
        finish_reason="stop",
        metadata={},
    )


def _markdown_to_html(markdown_text: str) -> str:
    """Natively converts Markdown text to standard HTML without external libraries."""
    html_lines = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <title>Generated Report</title>",
        "</head>",
        "<body>",
    ]
    in_list = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"  <h1>{line[2:].strip()}</h1>")
        elif line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"  <h2>{line[3:].strip()}</h2>")
        elif line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"  <h3>{line[4:].strip()}</h3>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("  <ul>")
                in_list = True
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line[2:].strip())
            html_lines.append(f"    <li>{text}</li>")
        else:
            if in_list:
                html_lines.append("  </ul>")
                in_list = False
            text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f"  <p>{text}</p>")

    if in_list:
        html_lines.append("  </ul>")

    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)


# ===========================================================================
# 📝 Story 1: Complete Developer Loop
# 1. Create a workspace folder.
# 2. Generate Python code (calculator.py).
# 3. Execute the generated code sandboxed.
# 4. If an error is raised, automatically parse stderr and apply a code fix.
# 5. Commit the finished file to Git.
# ===========================================================================

def test_story_1_complete_developer_loop(modules, tmp_path):
    """End-to-End Story 1: Complete Developer Loop with code generation, sandboxed execution, debug repair, and git commit."""
    fs_mod = modules["filesystem_v2"]
    py_mod = modules["python_runtime"]
    dev_mod = modules["developer"]
    git_mod = modules["git"]

    # Step 1: Create a workspace folder
    workspace = tmp_path / "dev_workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    calc_path = workspace / "calculator.py"

    # Step 2: Generate Python code (calculator.py) with an intentional flaw (ZeroDivisionError)
    flawed_code = (
        "def add(a, b):\n"
        "    return a + b\n\n"
        "def divide(a, b):\n"
        "    return a / b\n\n"
        "if __name__ == '__main__':\n"
        "    print(f'Add: {add(10, 5)}')\n"
        "    print(f'Divide: {divide(10, 0)}')\n"
    )
    fs_mod.write_file({"path": str(calc_path), "content": flawed_code})
    assert calc_path.exists()

    # Step 3: Execute the generated code sandboxed
    run_1 = py_mod.execute_script({"script_path": str(calc_path)})
    assert run_1["status"] == "FAILED"
    assert run_1["exit_code"] != 0
    assert "ZeroDivisionError" in run_1["stderr"]

    # Step 4: Automatically parse stderr and apply code fix via developer.debug_code
    fixed_code = (
        "def add(a, b):\n"
        "    return a + b\n\n"
        "def divide(a, b):\n"
        "    if b == 0:\n"
        "        return 0\n"
        "    return a / b\n\n"
        "if __name__ == '__main__':\n"
        "    print(f'Add: {add(10, 5)}')\n"
        "    print(f'Divide: {divide(10, 0)}')\n"
    )

    gw = dev_mod._get_model_gateway()
    with patch.object(gw, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = _mock_model_response(fixed_code)
        debug_res = dev_mod.debug_code({
            "file_path": str(calc_path),
            "error_message": run_1["stderr"],
        })
    assert debug_res["status"] == "SUCCESS"
    assert "fixed_code" in debug_res

    # Re-execute sandboxed: verify fix resolves error with exit code 0
    run_2 = py_mod.execute_script({"script_path": str(calc_path)})
    assert run_2["status"] == "SUCCESS"
    assert run_2["exit_code"] == 0
    assert "Divide: 0" in run_2["stdout"]

    # Step 5: Commit the finished file to Git
    subprocess.run(["git", "init"], cwd=str(workspace), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "developer@realtimex.io"], cwd=str(workspace), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Realtimex Developer"], cwd=str(workspace), check=True, capture_output=True)

    commit_res = git_mod.commit({
        "repo_path": str(workspace),
        "message": "feat: add robust calculator with zero division protection",
    })
    assert commit_res["status"] == "SUCCESS"

    # Verify commit in git log
    log = subprocess.run(["git", "log", "-1", "--oneline"], cwd=str(workspace), capture_output=True, text=True)
    assert "add robust calculator" in log.stdout


# ===========================================================================
# 📝 Story 2: Research & Report Generation
# 1. Download a remote webpage or retrieve content.
# 2. Summarize the text content.
# 3. Save the results as a Markdown file.
# 4. Convert Markdown to HTML natively.
# ===========================================================================

def test_story_2_research_and_report_generation(modules, tmp_path):
    """End-to-End Story 2: Research, summarization, Markdown generation, and native HTML rendering."""
    research_mod = modules["research"]
    summarizer_mod = modules["summarizer"]
    fs_mod = modules["filesystem_v2"]

    report_dir = tmp_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    md_path = report_dir / "reliability_report.md"
    html_path = report_dir / "reliability_report.html"

    # Step 1: Download or retrieve content from source
    simulated_body = (
        "Reliability engineering is a sub-discipline of systems engineering that emphasizes "
        "the ability of equipment to function without failure. Reliability describes the ability "
        "of a system or component to function under stated conditions for a specified period of time. "
        "Key aspects include MTBF (Mean Time Between Failures), failure rate, and availability."
    )
    gw = research_mod._get_model_gateway()
    with patch.object(gw, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = _mock_model_response(simulated_body)
        retrieval_res = research_mod.retrieve_content({"source": "https://example.com/reliability"})
    assert retrieval_res["status"] == "SUCCESS"
    assert "Reliability engineering" in retrieval_res["extracted_content"]

    # Step 2: Summarize the text content
    summary_markdown = (
        "# System Reliability Overview\n\n"
        "## Summary\n"
        "Reliability engineering focuses on system uptime, error prevention, and operational longevity.\n\n"
        "## Key Metrics\n"
        "- **MTBF**: Mean Time Between Failures\n"
        "- **Failure Rate**: Frequency of unanticipated stops\n"
        "- **Availability**: Percentage of functional uptime\n"
    )
    with patch.object(gw, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = _mock_model_response(summary_markdown)
        summary_res = summarizer_mod.summarize_text({"text": retrieval_res["extracted_content"]})
    assert summary_res["summary"] == summary_markdown

    # Step 3: Save the results as a Markdown file
    write_res = fs_mod.write_file({
        "path": str(md_path),
        "content": summary_res["summary"],
    })
    assert write_res["status"] == "SUCCESS"
    assert md_path.exists()
    assert md_path.stat().st_size > 0

    # Step 4: Convert Markdown to HTML natively and save
    html_content = _markdown_to_html(md_path.read_text(encoding="utf-8"))
    assert "<h1>System Reliability Overview</h1>" in html_content
    assert "<h2>Key Metrics</h2>" in html_content
    assert "<li><strong>MTBF</strong>: Mean Time Between Failures</li>" in html_content

    save_html_res = fs_mod.write_file({
        "path": str(html_path),
        "content": html_content,
    })
    assert save_html_res["status"] == "SUCCESS"
    assert html_path.exists()
    assert "<!DOCTYPE html>" in html_path.read_text(encoding="utf-8")


# ===========================================================================
# 📝 Story 3: Visual Intelligence & OCR Workflow
# 1. Take a screenshot or capture screen content.
# 2. Run OCR parsing on the visual asset.
# 3. Translate/describe structured observations from the parsed visual asset.
# 4. Summarize the key insights.
# ===========================================================================

def test_story_3_visual_intelligence_and_ocr_workflow(modules, tmp_path):
    """End-to-End Story 3: Visual capture, OCR text extraction, visual analysis, and insight summarization."""
    vision_mod = modules["vision"]
    summarizer_mod = modules["summarizer"]

    assets_dir = tmp_path / "visual_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    img_path = assets_dir / "system_dashboard.png"

    # Step 1: Capture screen content / create visual asset
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    img_path.write_bytes(png_bytes)
    assert img_path.exists()

    # Step 2: Run OCR parsing on the visual asset
    ocr_extracted_text = (
        "SYSTEM HEALTH DASHBOARD\n"
        "CPU Load: 14%\n"
        "Memory Usage: 3.2 MB / 10.0 MB Budget\n"
        "Scheduler Status: ACTIVE\n"
        "Active Workers: 9\n"
        "Active Tasks: 0\n"
        "System Reliability: 100.0%\n"
    )
    with patch.object(vision_mod, "_llm", return_value=ocr_extracted_text):
        ocr_res = vision_mod.extract_text({"path": str(img_path), "language": "en"})
    assert ocr_res["status"] == "SUCCESS"
    assert "SYSTEM HEALTH DASHBOARD" in ocr_res["extracted_text"]
    assert "System Reliability: 100.0%" in ocr_res["extracted_text"]

    # Step 3: Interpret / describe structured observations from the parsed visual asset
    visual_description = (
        "The image depicts an operational systems monitoring dashboard with all telemetry green. "
        "Resource utilization is well below configured thresholds with 3.2 MB RAM and 100% reliability."
    )
    with patch.object(vision_mod, "_llm", return_value=visual_description):
        desc_res = vision_mod.describe_screenshot({
            "path": str(img_path),
            "context": "Realtimex Operations Monitor"
        })
    assert desc_res["status"] == "SUCCESS"
    assert "telemetry green" in desc_res["ui_description"]

    # Step 4: Summarize the key insights
    dashboard_summary = (
        "System operational summary: All 9 worker pools are active with zero failures. "
        "Peak memory is safely bounded at 3.2 MB against the 10 MB budget. Status: HEALTHY."
    )
    gw = vision_mod._gateway()
    with patch.object(gw, "generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = _mock_model_response(dashboard_summary)
        summary_res = summarizer_mod.summarize_text({
            "text": f"{ocr_res['extracted_text']}\n{desc_res['ui_description']}"
        })
    assert "Status: HEALTHY" in summary_res["summary"]
    assert "3.2 MB" in summary_res["summary"]


# ===========================================================================
# 📝 Story 4: Complete Web Deployment
# 1. Generate static website files (HTML/CSS/JS).
# 2. Save to local hosting directories.
# 3. Open a browser session to verify navigation.
# 4. Validate page load statuses.
# ===========================================================================

def test_story_4_complete_web_deployment(modules, tmp_path):
    """End-to-End Story 4: Static website generation, local hosting deployment, browser navigation, and load validation."""
    fs_mod = modules["filesystem_v2"]
    browser_mod = modules["browser"]

    web_root = tmp_path / "public_html"
    web_root.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate static website files (HTML/CSS/JS)
    html_code = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>Realtimex Portfolio</title>\n"
        "  <link rel=\"stylesheet\" href=\"style.css\">\n"
        "</head>\n"
        "<body>\n"
        "  <header><h1>Welcome to Realtimex</h1></header>\n"
        "  <main><p id=\"status-msg\">System loaded successfully.</p></main>\n"
        "  <script src=\"app.js\"></script>\n"
        "</body>\n"
        "</html>"
    )
    css_code = "body { font-family: sans-serif; margin: 20px; background-color: #f4f4f4; }\nh1 { color: #2c3e50; }"
    js_code = "console.log('App loaded'); document.getElementById('status-msg').innerText = 'Ready and deployed.';"

    # Step 2: Save to local hosting directories
    res_html = fs_mod.write_file({"path": str(web_root / "index.html"), "content": html_code})
    res_css = fs_mod.write_file({"path": str(web_root / "style.css"), "content": css_code})
    res_js = fs_mod.write_file({"path": str(web_root / "app.js"), "content": js_code})

    assert res_html["status"] == "SUCCESS"
    assert res_css["status"] == "SUCCESS"
    assert res_js["status"] == "SUCCESS"
    assert (web_root / "index.html").exists()
    assert (web_root / "style.css").exists()
    assert (web_root / "app.js").exists()

    # Step 3: Open a browser session to verify navigation
    index_url = f"file://{web_root / 'index.html'}"
    simulated_browser_snapshot = (
        "Realtimex Portfolio\n"
        "Welcome to Realtimex\n"
        "Ready and deployed.\n"
    )
    with patch.object(browser_mod, "_llm", return_value=simulated_browser_snapshot):
        nav_res = browser_mod.navigate({"url": index_url})

    assert nav_res["status"] == "SUCCESS"
    assert nav_res["url"] == index_url
    assert "Realtimex Portfolio" in nav_res["page_snapshot"]

    # Step 4: Validate page load statuses
    with patch.object(browser_mod, "_llm", return_value="Ready and deployed."):
        content_res = browser_mod.extract_content({
            "url": index_url,
            "selector": "#status-msg",
            "description": "Deployment status message",
        })
    assert content_res["status"] == "SUCCESS"
    assert "Ready and deployed" in content_res["extracted_content"]
