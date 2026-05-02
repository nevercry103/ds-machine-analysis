# Reliability, Availability & Scalability (RAS) Design

**Scope:** How DS Machine Analyzer ensures data integrity, uptime, and scales to 10+ machines

---

## 1. Reliability (Data Integrity & Correctness)

### Zero Data Loss

**Requirement:** Every cycle captured is persisted; no data loss even on network failure

**Implementation:**

```
Transaction Safety:
  • Every cycle write wrapped in transaction
  • Commit only after persistence confirmed
  • Rollback on any error
  
  Code pattern:
    try:
      db_session.add(cycle)
      db_session.commit()  ← blocks until disk write
    except:
      db_session.rollback()
      raise
```

**Testing:**
- [ ] Chaos test: Kill DB during write → Verify rollback
- [ ] Network failure: Unplug PLC mid-cycle → Verify cache
- [ ] Power loss simulator: SQLite journal recovery

**Acceptance Criteria:**
- ✅ 1000 consecutive cycles → 1000 rows in database
- ✅ No duplicate cycles (unique cycle_id + timestamp)
- ✅ No missing steps within cycle

---

### Cycle Time Accuracy ≤10ms

**Requirement:** Cycle timestamp accuracy ±10ms vs. PLC clock

**Why:** This determines if we correctly identify slow steps

**Implementation:**

```
PLC Side:
  • Timestamp calculated at step complete (not network time)
  • PLC provides: timestamp_start (DTL), timestamp_end (DTL)
  • Python receives already-calculated duration

Python Side:
  • Read duration from PLC (don't recalculate)
  • Validate: end > start (must be true)
  • Store as-is (don't adjust based on network latency)

Validation:
  if cycle.timestamp_end < cycle.timestamp_start:
    raise ValueError("Invalid cycle: end < start")
  
  duration_ms = (timestamp_end - timestamp_start).total_seconds() * 1000
  if duration_ms < 0:
    raise ValueError("Negative duration not allowed")
```

**Testing:**
- [ ] Capture 100 cycles from real S7-1500
- [ ] Compare timestamps with TIA Portal offline viewer
- [ ] Verify ±10ms tolerance

**Acceptance Criteria:**
- ✅ Duration value matches PLC logged duration (within system clock precision)
- ✅ No outlier timestamps (e.g., future dates, year 2100)

---

### Graceful Error Handling

**Requirement:** Any error shows user-friendly message, doesn't crash UI

**Implementation:**

```
Error Boundary (PyQt6):
  try:
    result = process_cycle_data(cycle)
  except ValueError as e:
    logger.error(f"Invalid cycle data: {e}")
    show_toast("⚠ Cycle data issue", icon="warning", action="Details")
    return None
  except ConnectionError as e:
    logger.error(f"Database connection lost: {e}")
    show_toast("✗ Database offline", icon="error", action="Retry")
    queue_for_retry(cycle)
  except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    show_toast("✗ System error", icon="error", action="Support")

UI Never Shows:
  ✗ Blank screen
  ✗ Stack trace
  ✗ Unclear error message
  ✗ Unresponsive frozen UI
```

---

## 2. Availability (Uptime & Quick Recovery)

### Target: 99%+ Uptime (Mode 3 Laptop)

**Requirement:** System operational ≥99% of running hours

**Breakdown:**
- 100 hours/week operation
- 1 hour downtime allowed/week
- ≈8.6 minutes downtime/day average

**Implementation:**

```
Connection Watchdog:
  while True:
    if not is_connected_to_plc():
      attempt_reconnect()  ← 10s cooldown between attempts
      if reconnected:
        log("Reconnected to PLC")
      else:
        show_alert("PLC still offline")
        increment_retry_count()
        if retry_count > MAX_RETRIES:
          escalate_to_user("Manual intervention needed")
    
    await asyncio.sleep(5)  ← Check every 5s
```

**Automatic Recovery Scenarios:**

| Failure | Recovery | Time |
|---------|----------|------|
| Network hiccup (5s) | Auto-reconnect | <10s downtime |
| PLC reboot | Wait for PLC to boot, reconnect | <2min downtime |
| SQLite locked | Retry read/write transaction | <1s downtime |
| UI freeze | Async operations don't block UI | UI responsive |

**Testing:**
- [ ] Unplug Ethernet cable → Verify auto-reconnect
- [ ] Restart PLC → Verify cycle recovery
- [ ] Simulate DB lock → Verify retry logic
- [ ] Heavy load (100 cycles/min) → UI remains responsive

**Acceptance Criteria:**
- ✅ System recovers without user restart
- ✅ No data loss during connection loss
- ✅ UI responsive even during diagnostics

---

### Offline Mode (Laptop Commissioning)

**Requirement:** Continue limited operation when PLC unreachable

**Implementation:**

```
Offline State Detection:
  if no_connection_for(30_seconds):
    enter_offline_mode()
    background_color = #FFF59D  ← yellow overlay
    show_badge("OFFLINE MODE")
    show_message("Reconnecting in 5s...")

What Works Offline:
  ✓ View cached cycles (last hour)
  ✓ View statistics (local calculations)
  ✓ Export data (from cache)
  ✗ Cannot: Start new cycles, see real-time data

Queue Management:
  if PLC_reconnects:
    flush_pending_writes()
    resume_live_monitoring()
    clear_offline_badge()
```

---

## 3. Scalability

### Machine Scale: 1-10 Machines Per Instance

**Requirement:** Same app instance manages up to 10 machines simultaneously

**Architecture:**

```
Machine Registry (1:N pattern):
  registry = MachineRegistry()
  
  for machine_config in load_configs():
    machine = registry.register_machine(machine_config)
    
    adapter = OpcUaAdapter(machine.id, machine.protocol_config)
    processor = CycleProcessor(machine.id)
    
    data_bus = registry.get_data_bus(machine.id)
    await data_bus.subscribe("cycle_processor", processor.on_cycle_complete)

Each Machine:
  • 1 protocol adapter (e.g., OpcUaAdapter)
  • 1 data bus (event stream)
  • 1 cycle processor (statistics)
  • N subscribers (pillars)

Isolation:
  • Each machine's data bus is independent
  • No cross-machine data sharing
  • Failure in machine 1 doesn't affect machine 2
```

**Resource Usage (Laptop, per machine):**

```
Memory:     ~50-100 MB (cache + in-memory stats)
Disk I/O:   ~100KB/cycle (DB write)
Network:    ~50 frames/cycle × OPC-UA packet size (~2KB) = 100KB
CPU:        ~5-10% utilization (processing)

For 10 machines:
  Memory:   ~500-1000 MB (acceptable on 8GB laptop)
  Disk:     ~1MB/cycle → 1GB/day (typical)
  Network:  ~1MB/cycle (fast Ethernet handles easily)
```

**Testing:**
- [ ] Add 10 machines → Verify all cycle = independent
- [ ] Kill machine 3 connection → Verify 1,2,4..10 unaffected
- [ ] Memory profile: Run 1h → Check heap growth
- [ ] Disk I/O: Monitor write latency under 10 concurrent cycles

**Acceptance Criteria:**
- ✅ All 10 machines collect cycles simultaneously
- ✅ Failure in 1 machine doesn't block others
- ✅ Memory stable < 1GB after stabilization

---

### Database Scale (Laptop Mode 3)

**Requirement:** SQLite handles full cycle history (6-12 months)

**Scenarios:**

```
Scenario 1: Single machine, high-speed line
  Cycles/day: 10,000 (every 8.6s average)
  Days/month: 30
  Records/month: 300,000
  
  Data per cycle:
    • 1 cycle row: ~500 bytes
    • 5 step rows: ~250 bytes each
    • Total: ~1.75 KB per cycle
  
  Storage/month: 300k cycles × 1.75 KB = ~525 MB
  Storage/6 months: ~3.1 GB (acceptable on modern laptop)

Scenario 2: 10 machines, medium-speed
  Cycles/machine/day: 2,000
  Total cycles/day: 20,000
  Storage/6 months: ~64 GB (too much!)
  → Need archival strategy
```

**Archival Strategy:**

```
SQL Query Optimization:
  • Index on (machine_id, created_at)
  • Index on (cycle_id, machine_id)
  • Partition by month (logical, using date range)

Archival:
  • Keep last 3 months hot (SQLite)
  • Archive older months to CSV (compressed)
  • Option: Move to PostgreSQL Mode 2 (cloud)

Implementation:
  @daily_task
  def archive_old_cycles():
    90_days_ago = now() - timedelta(days=90)
    old_cycles = query(cycle.created_at < 90_days_ago)
    
    if len(old_cycles) > 0:
      filename = f"archive_{date}.csv.gz"
      export_cycles_to_csv(old_cycles, filename)
      
      # Delete from SQLite to free space
      delete_cycles(old_cycles.ids)
      
      logger.info(f"Archived {len(old_cycles)} cycles to {filename}")
```

**Testing:**
- [ ] Load 1 million cycles into SQLite → Measure query time
- [ ] Archive 500K cycles → Verify space freed
- [ ] Query on large table → Verify index performance

**Acceptance Criteria:**
- ✅ Query < 500ms (even with 1M rows)
- ✅ Archive process completes in <5 min
- ✅ Disk space reclaimed after archive

---

### Database Scale (Mode 2 PostgreSQL)

**Requirement:** PostgreSQL handles multi-machine, multi-customer

**Features:**

```
Multi-Partitioning:
  • Partition by (tenant_id, machine_id, date)
  • Enables parallel query execution
  • Automatic cleanup of old partitions

Replication:
  • Primary: Active reads/writes
  • Standby: Hot backup (same data)
  • Failover: Automatic on primary failure (<1min)

Connection Pooling:
  • pgBouncer: Max 100 connections (vs. unlimited)
  • Shared connection pool (efficient)
  • Auto-reconnect on pool exhaustion

Estimated Capacity:
  • Max customers: 100
  • Max machines/customer: 10 (1000 total)
  • Cycles/day: 20M
  • Storage growth: ~50GB/month
  • Query performance: <100ms (p99)
```

---

## 4. Performance Targets

### Response Time SLA

```
Operation | Target | Test Method
────────────────────────────────────────────
Page Load | <2s cold | Measure with DevTools
Navigation (tab) | <100ms | Measure UI frame time
Query (cycles table) | <500ms | SQLite 1M rows
Export CSV | <3s | 1000 cycles
Chart Render | <200ms | 100+ data points
PLC connection test | <5s | Real S7-1500
```

### Throughput SLA

```
Mode 3 (Laptop):
  • 1 machine: 100 cycles/min ✓
  • 10 machines: 100 cycles/min each ✓ (1000 total)
  • Network I/O: <100KB/s (OPC-UA frames)
  
Mode 2 (PostgreSQL):
  • 100 machines: 100 cycles/min each ✓ (10K total)
  • DB throughput: >1000 writes/sec
  • Query: <100ms (p99)
```

---

## 5. Testing Plan

### Reliability Testing

```
Phase 1: Data Integrity
  [ ] Insert 1000 cycles → Verify all 1000 rows
  [ ] Kill DB write → Verify rollback
  [ ] Duplicate cycle ID → Verify constraint error

Phase 2: Error Handling
  [ ] Invalid timestamp → Show user-friendly error
  [ ] Missing step → Log & continue
  [ ] Network timeout → Show toast, auto-retry
```

### Availability Testing

```
Phase 1: Connection Recovery
  [ ] Disconnect Ethernet → Auto-reconnect (< 10s)
  [ ] Network hiccup 5s → Transparent recovery
  [ ] PLC reboot → Reconnect after boot

Phase 2: Offline Mode
  [ ] Enter offline after 30s → Yellow badge
  [ ] Cached cycles viewable
  [ ] Reconnect → Resume live
```

### Scalability Testing

```
Phase 1: Multi-Machine
  [ ] Add 10 machines to registry
  [ ] All collect cycles simultaneously
  [ ] Kill machine 1 → Others unaffected

Phase 2: Database
  [ ] SQLite 1M rows → Query < 500ms
  [ ] Archive old cycles → Space freed
  [ ] Index performance on large table
```

---

## 6. Monitoring & Observability

### What to Monitor

```
System Health:
  • CPU usage > 80% → Alert
  • Memory usage > 80% → Alert
  • Disk full → Emergency alert
  • PLC connection lost > 5min → Alert

Application Health:
  • Cycle processing latency (target: <1s)
  • Export time (target: <3s)
  • UI response time (target: <100ms)
  • Database query time (target: <500ms)

Data Quality:
  • Cycles with missing steps
  • Out-of-order timestamps
  • Duplicate cycle IDs
  • Null/invalid values
```

### Metrics to Export

```
Prometheus Format:
  ds_machine_analyzer_cycles_total{machine_id="machine_001"} 1248
  ds_machine_analyzer_cycle_duration_seconds{machine_id="machine_001"} 2.34
  ds_machine_analyzer_db_query_duration_seconds 0.123
  ds_machine_analyzer_pplc_latency_ms 12
  ds_machine_analyzer_uptime_seconds 86400
```

---

## Checklist for RAS Review

### Reliability

- [ ] Transaction integrity: Can data loss occur?
- [ ] Error handling: Do errors show friendly messages?
- [ ] Validation: Are inputs validated (timestamps, IDs)?
- [ ] Audit trail: Can we trace data flow?

### Availability

- [ ] Watchdog: Does it auto-reconnect on failure?
- [ ] Recovery: Can system recover without restart?
- [ ] Deployment: Can we update without downtime?
- [ ] Backup: Is data backed up regularly?

### Scalability

- [ ] Machine isolation: Failure in 1 = others unaffected?
- [ ] Resource usage: CPU/Memory grows linearly (not exponential)?
- [ ] Database: Query performance stable >1M rows?
- [ ] Throughput: Can handle target load (100 cycles/min × 10 machines)?

---

**Document Owner:** DevOps + QA Lead  
**Last Updated:** 2026-05-02  
**Next Review:** End of Phase 1 (hardware testing cycle)
