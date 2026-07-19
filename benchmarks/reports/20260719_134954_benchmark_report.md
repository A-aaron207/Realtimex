# Realtimex Performance Benchmark Report

**Generated:** 2026-07-19 13:49:54  
**Total benchmark time:** 34.9s  
**Python:** 3.14.5  
**OS:** Linux 7.0.11-76070011-generic  
**Machine:** x86_64  
**Processor:** x86_64  

---

## Summary Table

```
Benchmark                                           Mean     Median        p95        Min        Max  Unit
----------------------------------------------------------------------------------------------------------
kernel.boot_time                                  0.7049     0.7125     0.7789     0.6317     0.7789  seconds
kernel.shutdown_time                              0.2331     0.2338     0.2587     0.1871     0.2587  seconds
kernel.boot_peak_memory                        3174.2881  3174.2881  3174.2881  3174.2881  3174.2881  KB
kernel.warm_boot_time                             0.6396     0.6119     0.7316     0.5554     0.7316  seconds
module_loader.full_load_time                      0.5504     0.5609     0.6365     0.4185     0.6365  seconds
module_loader.per_module_load_time               42.3390    43.1477    48.9598    32.1952    48.9598  ms
capability_registry.lookup_latency                0.0017     0.0011     0.0014     0.0010     0.4910  ms
module_loader.memory_footprint                    0.0000     0.0000     0.0000     0.0000     0.0000  KB
model_gateway.request_latency                     8.3427     2.3561     8.7383     1.1066   165.6713  ms
model_gateway.sequential_throughput             395.0069   395.0069   395.0069   395.0069   395.0069  req/sec
model_gateway.registry_lookup_latency             0.0007     0.0006     0.0009     0.0005     0.0076  ms
scheduler.task_submission_latency                95.6583    76.9168   581.6903    35.1581   581.6903  ms
scheduler.sequential_task_completion              0.2973     0.1616     0.8495     0.1484     0.8495  seconds
scheduler.concurrent_task_throughput              0.7247     0.7247     0.7247     0.7247     0.7247  tasks/sec
scheduler.concurrent_task_latency                 4.8297     1.2342    11.0248     1.0168    11.0248  seconds
```

---

## Detailed Results

### Kernel

#### `kernel.boot_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.7049** |
| Median | 0.7125 |
| Std Dev | 0.0544 |
| Min | 0.6317 |
| Max | 0.7789 |
| p95 | 0.7789 |

#### `kernel.shutdown_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.2331** |
| Median | 0.2338 |
| Std Dev | 0.0290 |
| Min | 0.1871 |
| Max | 0.2587 |
| p95 | 0.2587 |

#### `kernel.boot_peak_memory`

| Metric | Value |
|--------|-------|
| Unit | KB |
| Samples | 1 |
| Mean | **3174.2881** |
| Median | 3174.2881 |
| Std Dev | 0.0000 |
| Min | 3174.2881 |
| Max | 3174.2881 |
| p95 | 3174.2881 |

**Metadata:**
```json
{
  "note": "tracemalloc peak during boot()"
}
```

#### `kernel.warm_boot_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.6396** |
| Median | 0.6119 |
| Std Dev | 0.0750 |
| Min | 0.5554 |
| Max | 0.7316 |
| p95 | 0.7316 |

**Metadata:**
```json
{
  "note": "consecutive boot/shutdown in same process"
}
```

### Module Loader

#### `module_loader.full_load_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.5504** |
| Median | 0.5609 |
| Std Dev | 0.0814 |
| Min | 0.4185 |
| Max | 0.6365 |
| p95 | 0.6365 |

**Metadata:**
```json
{
  "module_count": 13
}
```

#### `module_loader.per_module_load_time`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 5 |
| Mean | **42.3390** |
| Median | 43.1477 |
| Std Dev | 6.2649 |
| Min | 32.1952 |
| Max | 48.9598 |
| p95 | 48.9598 |

**Metadata:**
```json
{
  "module_count": 13
}
```

#### `module_loader.memory_footprint`

| Metric | Value |
|--------|-------|
| Unit | KB |
| Samples | 1 |
| Mean | **0.0000** |
| Median | 0.0000 |
| Std Dev | 0.0000 |
| Min | 0.0000 |
| Max | 0.0000 |
| p95 | 0.0000 |

**Metadata:**
```json
{
  "module_count": 13
}
```

### Capability Registry

#### `capability_registry.lookup_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 1000 |
| Mean | **0.0017** |
| Median | 0.0011 |
| Std Dev | 0.0155 |
| Min | 0.0010 |
| Max | 0.4910 |
| p95 | 0.0014 |

**Metadata:**
```json
{
  "n": 1000,
  "total_capabilities": 55
}
```

### Model Gateway

#### `model_gateway.request_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 30 |
| Mean | **8.3427** |
| Median | 2.3561 |
| Std Dev | 29.7735 |
| Min | 1.1066 |
| Max | 165.6713 |
| p95 | 8.7383 |

**Metadata:**
```json
{
  "n": 30,
  "model": "llama3-70b-8192"
}
```

#### `model_gateway.sequential_throughput`

| Metric | Value |
|--------|-------|
| Unit | req/sec |
| Samples | 1 |
| Mean | **395.0069** |
| Median | 395.0069 |
| Std Dev | 0.0000 |
| Min | 395.0069 |
| Max | 395.0069 |
| p95 | 395.0069 |

**Metadata:**
```json
{
  "n": 50,
  "elapsed_s": 0.127
}
```

#### `model_gateway.registry_lookup_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 200 |
| Mean | **0.0007** |
| Median | 0.0006 |
| Std Dev | 0.0005 |
| Min | 0.0005 |
| Max | 0.0076 |
| p95 | 0.0009 |

**Metadata:**
```json
{
  "n": 200,
  "note": "ServiceRegistry.get_instance() overhead"
}
```

### Scheduler

#### `scheduler.task_submission_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 20 |
| Mean | **95.6583** |
| Median | 76.9168 |
| Std Dev | 116.0713 |
| Min | 35.1581 |
| Max | 581.6903 |
| p95 | 581.6903 |

**Metadata:**
```json
{
  "n": 20
}
```

#### `scheduler.sequential_task_completion`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.2973** |
| Median | 0.1616 |
| Std Dev | 0.3088 |
| Min | 0.1484 |
| Max | 0.8495 |
| p95 | 0.8495 |

**Metadata:**
```json
{
  "n": 5
}
```

#### `scheduler.concurrent_task_throughput`

| Metric | Value |
|--------|-------|
| Unit | tasks/sec |
| Samples | 1 |
| Mean | **0.7247** |
| Median | 0.7247 |
| Std Dev | 0.0000 |
| Min | 0.7247 |
| Max | 0.7247 |
| p95 | 0.7247 |

**Metadata:**
```json
{
  "concurrent_tasks": 8,
  "wall_time_s": 11.038,
  "individual_times": [
    1.022,
    1.017,
    1.079,
    1.203,
    1.265,
    11.025,
    11.014,
    11.013
  ]
}
```

#### `scheduler.concurrent_task_latency`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 8 |
| Mean | **4.8297** |
| Median | 1.2342 |
| Std Dev | 5.1245 |
| Min | 1.0168 |
| Max | 11.0248 |
| p95 | 11.0248 |

**Metadata:**
```json
{
  "concurrent_tasks": 8
}
```

---

## Performance Assessment

- **Boot time** `0.705s` — ⚠️ Acceptable (target: <0.5s)
- **Shutdown time** `0.233s` — ✅ Excellent (target: <0.3s)
- **Boot peak memory** `3,174 KB` — ✅ Lean (target: <50,000 KB)
- **Model request latency** `8.34ms` — ⚠️ Acceptable (target: <5ms simulated)
- **Task submission p95** `581.69ms` — ❌ Slow (target: <10ms)
- **Capability registry p95** `0.0014ms` — ✅ Fast (target: <0.1ms)

---

*Generated by Realtimex Benchmark Suite v1.0*