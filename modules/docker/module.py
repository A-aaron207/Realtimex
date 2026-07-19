"""
Docker Module entry point.

Provides containerised execution capabilities:
- build_image        — build a Docker image from a Dockerfile
- run_container      — start a container from an image
- stop_container     — stop (and optionally remove) a running container
- list_containers    — list running or all containers
- exec_in_container  — execute a command inside a running container
"""

from __future__ import annotations

import subprocess
from typing import Any

from loader.module_base import ModuleEntryPoint

_DOCKER_TIMEOUT = 120.0   # generous cap for build operations
_DEFAULT_TIMEOUT = 30.0


def _docker(*args: str, cwd: str | None = None, timeout: float = _DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Run `docker <args>` and return a structured result."""
    try:
        result = subprocess.run(
            ["docker"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"status": "FAILED", "error": "Docker command timed out.", "exit_code": -1}
    except FileNotFoundError:
        return {"status": "FAILED", "error": "docker executable not found. Is Docker installed?", "exit_code": -1}
    except Exception as exc:
        return {"status": "FAILED", "error": str(exc), "exit_code": -1}


class Module(ModuleEntryPoint):
    """Entry point for the Docker Module."""

    module_id = "docker"
    capabilities = [
        "build_image",
        "run_container",
        "stop_container",
        "list_containers",
        "exec_in_container",
    ]

    def describe(self) -> str:
        return "Provides Docker container lifecycle management: build, run, stop, list, and exec."

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    def build_image(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Build a Docker image from a Dockerfile."""
        tag = input_data.get("tag") or input_data.get("name")
        context_path = input_data.get("context_path", ".")
        dockerfile = input_data.get("dockerfile")        # optional path to Dockerfile
        build_args = input_data.get("build_args", {})    # dict of ARG_NAME -> value

        if not tag:
            return {"status": "FAILED", "error": "No image tag provided."}

        args = ["build", "-t", tag]
        if dockerfile:
            args += ["-f", dockerfile]
        for k, v in build_args.items():
            args += ["--build-arg", f"{k}={v}"]
        args.append(context_path)

        result = _docker(*args, cwd=context_path, timeout=_DOCKER_TIMEOUT)
        result["image_tag"] = tag
        return result

    def run_container(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Start a container from an image and return its container ID."""
        image = input_data.get("image")
        name = input_data.get("name")                    # optional container name
        detach = input_data.get("detach", True)
        ports = input_data.get("ports", {})              # {"8080": "80"} host:container
        env_vars = input_data.get("env", {})             # {"KEY": "value"}
        volumes = input_data.get("volumes", {})          # {"host_path": "container_path"}
        command = input_data.get("command")              # override CMD

        if not image:
            return {"status": "FAILED", "error": "No image name provided."}

        args = ["run"]
        if detach:
            args.append("-d")
        if name:
            args += ["--name", name]
        for host_port, cont_port in ports.items():
            args += ["-p", f"{host_port}:{cont_port}"]
        for k, v in env_vars.items():
            args += ["-e", f"{k}={v}"]
        for host_vol, cont_vol in volumes.items():
            args += ["-v", f"{host_vol}:{cont_vol}"]
        args.append(image)
        if command:
            args += command if isinstance(command, list) else command.split()

        result = _docker(*args)
        if result["status"] == "SUCCESS":
            result["container_id"] = result["stdout"][:12]
        return result

    def stop_container(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Stop a running container, optionally removing it."""
        container = input_data.get("container") or input_data.get("container_id")
        remove = input_data.get("remove", False)
        timeout_sec = int(input_data.get("timeout_sec", 10))

        if not container:
            return {"status": "FAILED", "error": "No container name or ID provided."}

        result = _docker("stop", "-t", str(timeout_sec), container)

        if result["status"] == "SUCCESS" and remove:
            rm_result = _docker("rm", container)
            result["removed"] = rm_result["status"] == "SUCCESS"
        else:
            result["removed"] = False

        return result

    def list_containers(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """List containers. Returns running containers by default; set all=true for all."""
        all_containers = input_data.get("all", False)
        filter_name = input_data.get("filter_name")      # optional name substring filter

        args = ["ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]
        if all_containers:
            args.append("-a")
        if filter_name:
            args += ["--filter", f"name={filter_name}"]

        result = _docker(*args)
        if result["status"] == "SUCCESS":
            containers = []
            for line in result["stdout"].splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                containers.append({
                    "id": parts[0] if len(parts) > 0 else "",
                    "name": parts[1] if len(parts) > 1 else "",
                    "image": parts[2] if len(parts) > 2 else "",
                    "status": parts[3] if len(parts) > 3 else "",
                    "ports": parts[4] if len(parts) > 4 else ""
                })
            result["containers"] = containers
            result["count"] = len(containers)
        return result

    def exec_in_container(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute a command inside a running container."""
        container = input_data.get("container") or input_data.get("container_id")
        command = input_data.get("command")
        workdir = input_data.get("workdir")
        user = input_data.get("user")

        if not container:
            return {"status": "FAILED", "error": "No container name or ID provided."}
        if not command:
            return {"status": "FAILED", "error": "No command provided."}

        args = ["exec"]
        if workdir:
            args += ["-w", workdir]
        if user:
            args += ["-u", user]
        args.append(container)

        if isinstance(command, list):
            args += command
        else:
            args += ["sh", "-c", command]

        return _docker(*args)

    def execute(self, capability: str, context: Any) -> dict[str, Any]:
        """Standardized entry point mapping execution requests to methods."""
        dispatch = {
            "build_image": self.build_image,
            "run_container": self.run_container,
            "stop_container": self.stop_container,
            "list_containers": self.list_containers,
            "exec_in_container": self.exec_in_container,
        }
        if capability not in dispatch:
            raise NotImplementedError(f"Capability '{capability}' not supported by Docker Module.")
        return dispatch[capability](context.input)
