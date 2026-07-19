# Realtimex Performance Benchmark Report

**Generated:** 2026-07-19 13:49:00  
**Total benchmark time:** 33.9s  
**Python:** 3.14.5  
**OS:** Linux 7.0.11-76070011-generic  
**Machine:** x86_64  
**Processor:** x86_64  

---

## Summary Table

```
Benchmark                                           Mean     Median        p95        Min        Max  Unit
----------------------------------------------------------------------------------------------------------
kernel.boot_time                                  0.5780     0.5747     0.6212     0.5257     0.6212  seconds
kernel.shutdown_time                              0.2635     0.2579     0.2975     0.2301     0.2975  seconds
kernel.boot_peak_memory                        2884.9717  2884.9717  2884.9717  2884.9717  2884.9717  KB
kernel.warm_boot_time                             0.5549     0.5389     0.7048     0.4600     0.7048  seconds
module_loader.full_load_time                      0.4870     0.5032     0.5740     0.4085     0.5740  seconds
module_loader.per_module_load_time               37.4649    38.7065    44.1545    31.4259    44.1545  ms
capability_registry.lookup_latency                0.0014     0.0011     0.0015     0.0008     0.0686  ms
module_loader.memory_footprint                    0.0000     0.0000     0.0000     0.0000     0.0000  KB
model_gateway.request_latency                     8.1448     1.8098     7.0599     1.3833   171.7595  ms
model_gateway.sequential_throughput             405.4282   405.4282   405.4282   405.4282   405.4282  req/sec
model_gateway.registry_lookup_latency             0.0006     0.0006     0.0008     0.0005     0.0048  ms
scheduler.task_submission_latency               108.5256    84.1084   551.6778    45.1060   551.6778  ms
scheduler.sequential_task_completion              0.2716     0.1344     0.8402     0.1048     0.8402  seconds
scheduler.concurrent_task_throughput              0.7193     0.7193     0.7193     0.7193     0.7193  tasks/sec
scheduler.concurrent_task_latency                 3.6989     1.2882    11.1196     1.1171    11.1196  seconds
```

---

## Detailed Results

### Kernel

#### `kernel.boot_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.5780** |
| Median | 0.5747 |
| Std Dev | 0.0356 |
| Min | 0.5257 |
| Max | 0.6212 |
| p95 | 0.6212 |

#### `kernel.shutdown_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.2635** |
| Median | 0.2579 |
| Std Dev | 0.0313 |
| Min | 0.2301 |
| Max | 0.2975 |
| p95 | 0.2975 |

#### `kernel.boot_peak_memory`

| Metric | Value |
|--------|-------|
| Unit | KB |
| Samples | 1 |
| Mean | **2884.9717** |
| Median | 2884.9717 |
| Std Dev | 0.0000 |
| Min | 2884.9717 |
| Max | 2884.9717 |
| p95 | 2884.9717 |

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
| Mean | **0.5549** |
| Median | 0.5389 |
| Std Dev | 0.0913 |
| Min | 0.4600 |
| Max | 0.7048 |
| p95 | 0.7048 |

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
| Mean | **0.4870** |
| Median | 0.5032 |
| Std Dev | 0.0641 |
| Min | 0.4085 |
| Max | 0.5740 |
| p95 | 0.5740 |

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
| Mean | **37.4649** |
| Median | 38.7065 |
| Std Dev | 4.9303 |
| Min | 31.4259 |
| Max | 44.1545 |
| p95 | 44.1545 |

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
| Mean | **0.0014** |
| Median | 0.0011 |
| Std Dev | 0.0034 |
| Min | 0.0008 |
| Max | 0.0686 |
| p95 | 0.0015 |

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
| Mean | **8.1448** |
| Median | 1.8098 |
| Std Dev | 30.9327 |
| Min | 1.3833 |
| Max | 171.7595 |
| p95 | 7.0599 |

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
| Mean | **405.4282** |
| Median | 405.4282 |
| Std Dev | 0.0000 |
| Min | 405.4282 |
| Max | 405.4282 |
| p95 | 405.4282 |

**Metadata:**
```json
{
  "n": 50,
  "elapsed_s": 0.123
}
```

#### `model_gateway.registry_lookup_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 200 |
| Mean | **0.0006** |
| Median | 0.0006 |
| Std Dev | 0.0003 |
| Min | 0.0005 |
| Max | 0.0048 |
| p95 | 0.0008 |

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
| Mean | **108.5256** |
| Median | 84.1084 |
| Std Dev | 107.1845 |
| Min | 45.1060 |
| Max | 551.6778 |
| p95 | 551.6778 |

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
| Mean | **0.2716** |
| Median | 0.1344 |
| Std Dev | 0.3183 |
| Min | 0.1048 |
| Max | 0.8402 |
| p95 | 0.8402 |

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
| Mean | **0.7193** |
| Median | 0.7193 |
| Std Dev | 0.0000 |
| Min | 0.7193 |
| Max | 0.7193 |
| p95 | 0.7193 |

**Metadata:**
```json
{
  "concurrent_tasks": 8,
  "wall_time_s": 11.123,
  "individual_times": [
    1.117,
    1.118,
    1.176,
    1.253,
    1.323,
    1.367,
    11.12,
    11.117
  ]
}
```

#### `scheduler.concurrent_task_latency`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 8 |
| Mean | **3.6989** |
| Median | 1.2882 |
| Std Dev | 4.5802 |
| Min | 1.1171 |
| Max | 11.1196 |
| p95 | 11.1196 |

**Metadata:**
```json
{
  "concurrent_tasks": 8
}
```

---

## Performance Assessment

- **Boot time** `0.578s` — ⚠️ Acceptable (target: <0.5s)
- **Shutdown time** `0.263s` — ✅ Excellent (target: <0.3s)
- **Boot peak memory** `2,885 KB` — ✅ Lean (target: <50,000 KB)
- **Model request latency** `8.14ms` — ⚠️ Acceptable (target: <5ms simulated)
- **Task submission p95** `551.68ms` — ❌ Slow (target: <10ms)
- **Capability registry p95** `0.0015ms` — ✅ Fast (target: <0.1ms)

---

*Generated by Realtimex Benchmark Suite v1.0*