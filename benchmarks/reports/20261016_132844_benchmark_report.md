# Realtimex Performance Benchmark Report

**Generated:** 2026-10-16 13:28:44  
**Total benchmark time:** 29.0s  
**Python:** 3.13.5  
**OS:** Linux 6.12.111+deb13-amd64  
**Machine:** x86_64  
**Processor:** x86_64  

---

## Summary Table

```
Benchmark                                           Mean     Median        p95        Min        Max  Unit
----------------------------------------------------------------------------------------------------------
kernel.boot_time                                  0.4087     0.4054     0.4396     0.3862     0.4396  seconds
kernel.shutdown_time                              0.3463     0.3462     0.3698     0.3320     0.3698  seconds
kernel.boot_peak_memory                        1455.8037  1455.8037  1455.8037  1455.8037  1455.8037  KB
kernel.warm_boot_time                             0.4106     0.4091     0.4224     0.3926     0.4224  seconds
event_bus.publish_latency                         0.0432     0.0277     0.0452     0.0164     3.0253  ms
event_bus.burst_throughput                    16436.1337 16436.1337 16436.1337 16436.1337 16436.1337  events/sec
event_bus.subscribe_rtt_latency                   0.0740     0.0361     0.1595     0.0304     2.7118  ms
event_bus.concurrent_throughput               116508.2863 116508.2863 116508.2863 116508.2863 116508.2863  events/sec
module_loader.full_load_time                      0.4744     0.5040     0.5160     0.3598     0.5160  seconds
module_loader.per_module_load_time               36.4892    38.7678    39.6912    27.6740    39.6912  ms
capability_registry.lookup_latency                0.0011     0.0009     0.0015     0.0007     0.0403  ms
module_loader.memory_footprint                    0.0000     0.0000     0.0000     0.0000     0.0000  KB
model_gateway.request_latency                     5.1824     1.8051    17.2011     0.9511    74.7517  ms
model_gateway.sequential_throughput             479.5726   479.5726   479.5726   479.5726   479.5726  req/sec
model_gateway.registry_lookup_latency             0.0004     0.0002     0.0005     0.0002     0.0085  ms
scheduler.task_submission_latency                46.3584    44.3114    81.3115     9.2730    81.3115  ms
scheduler.sequential_task_completion              0.1347     0.1371     0.2515     0.0047     0.2515  seconds
scheduler.concurrent_task_throughput              0.7626     0.7626     0.7626     0.7626     0.7626  tasks/sec
scheduler.concurrent_task_latency                 8.0320    10.4450    10.4759     0.8141    10.4759  seconds
```

---

## Detailed Results

### Kernel

#### `kernel.boot_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.4087** |
| Median | 0.4054 |
| Std Dev | 0.0222 |
| Min | 0.3862 |
| Max | 0.4396 |
| p95 | 0.4396 |

#### `kernel.shutdown_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.3463** |
| Median | 0.3462 |
| Std Dev | 0.0150 |
| Min | 0.3320 |
| Max | 0.3698 |
| p95 | 0.3698 |

#### `kernel.boot_peak_memory`

| Metric | Value |
|--------|-------|
| Unit | KB |
| Samples | 1 |
| Mean | **1455.8037** |
| Median | 1455.8037 |
| Std Dev | 0.0000 |
| Min | 1455.8037 |
| Max | 1455.8037 |
| p95 | 1455.8037 |

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
| Mean | **0.4106** |
| Median | 0.4091 |
| Std Dev | 0.0121 |
| Min | 0.3926 |
| Max | 0.4224 |
| p95 | 0.4224 |

**Metadata:**
```json
{
  "note": "consecutive boot/shutdown in same process"
}
```

### Event Bus

#### `event_bus.publish_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 500 |
| Mean | **0.0432** |
| Median | 0.0277 |
| Std Dev | 0.1701 |
| Min | 0.0164 |
| Max | 3.0253 |
| p95 | 0.0452 |

**Metadata:**
```json
{
  "n": 500
}
```

#### `event_bus.burst_throughput`

| Metric | Value |
|--------|-------|
| Unit | events/sec |
| Samples | 1 |
| Mean | **16436.1337** |
| Median | 16436.1337 |
| Std Dev | 0.0000 |
| Min | 16436.1337 |
| Max | 16436.1337 |
| p95 | 16436.1337 |

**Metadata:**
```json
{
  "n": 2000,
  "elapsed_s": 0.1217
}
```

#### `event_bus.subscribe_rtt_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 200 |
| Mean | **0.0740** |
| Median | 0.0361 |
| Std Dev | 0.2148 |
| Min | 0.0304 |
| Max | 2.7118 |
| p95 | 0.1595 |

**Metadata:**
```json
{
  "n": 200
}
```

#### `event_bus.concurrent_throughput`

| Metric | Value |
|--------|-------|
| Unit | events/sec |
| Samples | 1 |
| Mean | **116508.2863** |
| Median | 116508.2863 |
| Std Dev | 0.0000 |
| Min | 116508.2863 |
| Max | 116508.2863 |
| p95 | 116508.2863 |

**Metadata:**
```json
{
  "threads": 8,
  "events_per_thread": 250,
  "total_events": 2000
}
```

### Module Loader

#### `module_loader.full_load_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.4744** |
| Median | 0.5040 |
| Std Dev | 0.0652 |
| Min | 0.3598 |
| Max | 0.5160 |
| p95 | 0.5160 |

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
| Mean | **36.4892** |
| Median | 38.7678 |
| Std Dev | 5.0191 |
| Min | 27.6740 |
| Max | 39.6912 |
| p95 | 39.6912 |

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
| Mean | **0.0011** |
| Median | 0.0009 |
| Std Dev | 0.0013 |
| Min | 0.0007 |
| Max | 0.0403 |
| p95 | 0.0015 |

**Metadata:**
```json
{
  "n": 1000,
  "total_capabilities": 56
}
```

### Model Gateway

#### `model_gateway.request_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 30 |
| Mean | **5.1824** |
| Median | 1.8051 |
| Std Dev | 13.5087 |
| Min | 0.9511 |
| Max | 74.7517 |
| p95 | 17.2011 |

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
| Mean | **479.5726** |
| Median | 479.5726 |
| Std Dev | 0.0000 |
| Min | 479.5726 |
| Max | 479.5726 |
| p95 | 479.5726 |

**Metadata:**
```json
{
  "n": 50,
  "elapsed_s": 0.104
}
```

#### `model_gateway.registry_lookup_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 200 |
| Mean | **0.0004** |
| Median | 0.0002 |
| Std Dev | 0.0008 |
| Min | 0.0002 |
| Max | 0.0085 |
| p95 | 0.0005 |

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
| Mean | **46.3584** |
| Median | 44.3114 |
| Std Dev | 17.9600 |
| Min | 9.2730 |
| Max | 81.3115 |
| p95 | 81.3115 |

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
| Mean | **0.1347** |
| Median | 0.1371 |
| Std Dev | 0.0875 |
| Min | 0.0047 |
| Max | 0.2515 |
| p95 | 0.2515 |

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
| Mean | **0.7626** |
| Median | 0.7626 |
| Std Dev | 0.0000 |
| Min | 0.7626 |
| Max | 0.7626 |
| p95 | 0.7626 |

**Metadata:**
```json
{
  "concurrent_tasks": 8,
  "wall_time_s": 10.49,
  "individual_times": [
    0.814,
    0.869,
    10.282,
    10.443,
    10.448,
    10.453,
    10.471,
    10.476
  ]
}
```

#### `scheduler.concurrent_task_latency`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 8 |
| Mean | **8.0320** |
| Median | 10.4450 |
| Std Dev | 4.4384 |
| Min | 0.8141 |
| Max | 10.4759 |
| p95 | 10.4759 |

**Metadata:**
```json
{
  "concurrent_tasks": 8
}
```

---

## Performance Assessment

- **Boot time** `0.409s` — ✅ Excellent (target: <0.5s)
- **Shutdown time** `0.346s` — ⚠️ Acceptable (target: <0.3s)
- **Boot peak memory** `1,456 KB` — ✅ Lean (target: <50,000 KB)
- **Event publish p95** `0.045ms` — ✅ Fast (target: <1ms)
- **Event burst throughput** `16,436 events/s` — ✅ High (target: >10,000/s)
- **Event subscribe RTT p95** `0.159ms` — ✅ Fast (target: <5ms)
- **Model request latency** `5.18ms` — ⚠️ Acceptable (target: <5ms simulated)
- **Task submission p95** `81.31ms` — ❌ Slow (target: <10ms)
- **Capability registry p95** `0.0015ms` — ✅ Fast (target: <0.1ms)

---

*Generated by Realtimex Benchmark Suite v1.0*