# Realtimex Platform — Known Limitations & Constraints

This document lists the deliberate engineering boundaries, security constraints, and performance limitations of the Realtimex Platform v1.0. These boundaries set the appropriate expectations for developers, beta testers, and future contributors.

---

## 🖥️ Operating System Support

### Linux & Raspberry Pi (Target Platforms)
* **Status**: Fully Supported
* **Limitations**: 
  - Directory watching uses a polling-based watcher. While compatible without third-party dependencies, it is less efficient than system-level inotify notifications on massive folder structures.
  - Native desktop notifications require `notify-send` to be installed on the system; otherwise, notifications fall back to logs and system bell beeps.

### Windows (Compatibility Platform)
* **Status**: Compatible (Partially Simulated in non-Windows host tests)
* **Limitations**:
  - The process terminal runner defaults to `cmd.exe` or `powershell.exe`. Standard POSIX-specific shell commands invoked by core modules might fail unless wrapped in Windows-compatible syntax.
  - System sound uses standard `winsound` calls, which require native Windows sound card drivers.

---

## 🔒 Security & Sandbox Boundaries

* **No Process-Level Namespacing**: The permission manager cache and sandbox checks operate at the Python application level (via metadata and manifest checking). It does not enforce hard kernel-level OS namespaces (such as cgroups, chroot, or Docker-like virtualization namespaces) inside the python runtime unless specifically run inside the Docker Module.
* **Implicit Trust in Module Loader**: Modules loaded from the `modules/` folder are assumed to have valid manifest declarations. Malicious code could bypass local validation if files are modified directly on disk post-validation.

---

## ⚡ Performance Limits & Bottlenecks

* **Disk I/O Concurrency Contention**: 
  - While independent systems (Memory Manager, Workflow Engine, Task Repository) load in parallel threads to speed up boot times, they perform synchronous disk reading. Under high disk contention (e.g. on slow spinning media HDD), this concurrency can cause individual subsystem load timings to increase.
* **Memory Index Scaling**:
  - Memory Manager loads indices into process memory at boot time. For environments with tens of thousands of complex context histories, this will lead to increased RAM utilization and slower startup times. Deferring this via lazy loading is postponed to v1.1.

---

## 🗺️ Scope Postponements (Moved to v1.1 / v2.0)

* **Multi-Agent Collaboration**: Cross-kernel routing and peer-to-peer task exchange are not supported in v1.0 (slated for v2.0).
* **Interactive First-Run Wizard**: Setup API connectivity prompts and environment config generation must be edited manually in `config/config.json` for v1.0 (wizard planned for v1.1).
