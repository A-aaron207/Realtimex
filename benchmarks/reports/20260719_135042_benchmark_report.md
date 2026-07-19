# Realtimex Performance Benchmark Report

**Generated:** 2026-07-19 13:50:42  
**Total benchmark time:** 35.5s  
**Python:** 3.14.5  
**OS:** Linux 7.0.11-76070011-generic  
**Machine:** x86_64  
**Processor:** x86_64  

---

## Summary Table

```
Benchmark                                           Mean     Median        p95        Min        Max  Unit
----------------------------------------------------------------------------------------------------------
kernel.boot_time                                  0.6377     0.6279     0.6984     0.5982     0.6984  seconds
kernel.shutdown_time                              0.2585     0.2442     0.2987     0.2326     0.2987  seconds
kernel.boot_peak_memory                        3485.9180  3485.9180  3485.9180  3485.9180  3485.9180  KB
kernel.warm_boot_time                             0.6714     0.6436     0.7501     0.5842     0.7501  seconds
event_bus.publish_latency                         0.0781     0.0452     0.1546     0.0211     3.2159  ms
event_bus.burst_throughput                    17134.7766 17134.7766 17134.7766 17134.7766 17134.7766  events/sec
event_bus.subscribe_rtt_latency                   0.0947     0.0527     0.1911     0.0357     2.8699  ms
event_bus.concurrent_throughput               22212.9777 22212.9777 22212.9777 22212.9777 22212.9777  events/sec
module_loader.full_load_time                      0.5695     0.5732     0.6001     0.5289     0.6001  seconds
module_loader.per_module_load_time               43.8102    44.0949    46.1637    40.6827    46.1637  ms
capability_registry.lookup_latency                0.0016     0.0013     0.0027     0.0007     0.0216  ms
module_loader.memory_footprint                    0.0000     0.0000     0.0000     0.0000     0.0000  KB
model_gateway.request_latency                     8.3468     2.5880     6.0740     1.3886   165.9449  ms
model_gateway.sequential_throughput             455.0985   455.0985   455.0985   455.0985   455.0985  req/sec
model_gateway.registry_lookup_latency             0.0008     0.0006     0.0010     0.0005     0.0255  ms
scheduler.task_submission_latency                99.8172    71.5511   568.7427    39.1112   568.7427  ms
scheduler.sequential_task_completion              0.2833     0.1572     0.8155     0.1255     0.8155  seconds
scheduler.concurrent_task_throughput              0.7154     0.7154     0.7154     0.7154     0.7154  tasks/sec
scheduler.concurrent_task_latency                 3.7459     1.3175    11.1751     1.1693    11.1751  seconds
```

---

## Detailed Results

### Kernel

#### `kernel.boot_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.6377** |
| Median | 0.6279 |
| Std Dev | 0.0396 |
| Min | 0.5982 |
| Max | 0.6984 |
| p95 | 0.6984 |

#### `kernel.shutdown_time`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 5 |
| Mean | **0.2585** |
| Median | 0.2442 |
| Std Dev | 0.0307 |
| Min | 0.2326 |
| Max | 0.2987 |
| p95 | 0.2987 |

#### `kernel.boot_peak_memory`

| Metric | Value |
|--------|-------|
| Unit | KB |
| Samples | 1 |
| Mean | **3485.9180** |
| Median | 3485.9180 |
| Std Dev | 0.0000 |
| Min | 3485.9180 |
| Max | 3485.9180 |
| p95 | 3485.9180 |

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
| Mean | **0.6714** |
| Median | 0.6436 |
| Std Dev | 0.0721 |
| Min | 0.5842 |
| Max | 0.7501 |
| p95 | 0.7501 |

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
| Mean | **0.0781** |
| Median | 0.0452 |
| Std Dev | 0.2207 |
| Min | 0.0211 |
| Max | 3.2159 |
| p95 | 0.1546 |

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
| Mean | **17134.7766** |
| Median | 17134.7766 |
| Std Dev | 0.0000 |
| Min | 17134.7766 |
| Max | 17134.7766 |
| p95 | 17134.7766 |

**Metadata:**
```json
{
  "n": 2000,
  "elapsed_s": 0.1167
}
```

#### `event_bus.subscribe_rtt_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 200 |
| Mean | **0.0947** |
| Median | 0.0527 |
| Std Dev | 0.2268 |
| Min | 0.0357 |
| Max | 2.8699 |
| p95 | 0.1911 |

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
| Mean | **22212.9777** |
| Median | 22212.9777 |
| Std Dev | 0.0000 |
| Min | 22212.9777 |
| Max | 22212.9777 |
| p95 | 22212.9777 |

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
| Mean | **0.5695** |
| Median | 0.5732 |
| Std Dev | 0.0270 |
| Min | 0.5289 |
| Max | 0.6001 |
| p95 | 0.6001 |

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
| Mean | **43.8102** |
| Median | 44.0949 |
| Std Dev | 2.0764 |
| Min | 40.6827 |
| Max | 46.1637 |
| p95 | 46.1637 |

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
| Mean | **0.0016** |
| Median | 0.0013 |
| Std Dev | 0.0011 |
| Min | 0.0007 |
| Max | 0.0216 |
| p95 | 0.0027 |

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
| Mean | **8.3468** |
| Median | 2.5880 |
| Std Dev | 29.7886 |
| Min | 1.3886 |
| Max | 165.9449 |
| p95 | 6.0740 |

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
| Mean | **455.0985** |
| Median | 455.0985 |
| Std Dev | 0.0000 |
| Min | 455.0985 |
| Max | 455.0985 |
| p95 | 455.0985 |

**Metadata:**
```json
{
  "n": 50,
  "elapsed_s": 0.11
}
```

#### `model_gateway.registry_lookup_latency`

| Metric | Value |
|--------|-------|
| Unit | ms |
| Samples | 200 |
| Mean | **0.0008** |
| Median | 0.0006 |
| Std Dev | 0.0018 |
| Min | 0.0005 |
| Max | 0.0255 |
| p95 | 0.0010 |

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
| Mean | **99.8172** |
| Median | 71.5511 |
| Std Dev | 112.4366 |
| Min | 39.1112 |
| Max | 568.7427 |
| p95 | 568.7427 |

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
| Mean | **0.2833** |
| Median | 0.1572 |
| Std Dev | 0.2982 |
| Min | 0.1255 |
| Max | 0.8155 |
| p95 | 0.8155 |

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
| Mean | **0.7154** |
| Median | 0.7154 |
| Std Dev | 0.0000 |
| Min | 0.7154 |
| Max | 0.7154 |
| p95 | 0.7154 |

**Metadata:**
```json
{
  "concurrent_tasks": 8,
  "wall_time_s": 11.182,
  "individual_times": [
    1.169,
    1.175,
    1.219,
    1.287,
    1.348,
    1.42,
    11.174,
    11.175
  ]
}
```

#### `scheduler.concurrent_task_latency`

| Metric | Value |
|--------|-------|
| Unit | seconds |
| Samples | 8 |
| Mean | **3.7459** |
| Median | 1.3175 |
| Std Dev | 4.5858 |
| Min | 1.1693 |
| Max | 11.1751 |
| p95 | 11.1751 |

**Metadata:**
```json
{
  "concurrent_tasks": 8
}
```

---

## Performance Assessment

- **Boot time** `0.638s` — ⚠️ Acceptable (target: <0.5s)
- **Shutdown time** `0.259s` — ✅ Excellent (target: <0.3s)
- **Boot peak memory** `3,486 KB` — ✅ Lean (target: <50,000 KB)
- **Event publish p95** `0.155ms` — ✅ Fast (target: <1ms)
- **Event burst throughput** `17,135 events/s` — ✅ High (target: >10,000/s)
- **Event subscribe RTT p95** `0.191ms` — ✅ Fast (target: <5ms)
- **Model request latency** `8.35ms` — ⚠️ Acceptable (target: <5ms simulated)
- **Task submission p95** `568.74ms` — ❌ Slow (target: <10ms)
- **Capability registry p95** `0.0027ms` — ✅ Fast (target: <0.1ms)

---

*Generated by Realtimex Benchmark Suite v1.0*