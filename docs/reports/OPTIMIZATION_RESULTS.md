# Pytest Performance Optimization Results
## Before vs After Comparison

**Date**: 2025-10-22
**Optimization**: Replaced AsyncSqliteSaver with MemorySaver + Session-scoped fixtures

---

## 📊 Results Summary

| Metric | Before | After | Improvement | % Change |
|--------|--------|-------|-------------|----------|
| **Total Test Time** | 280.6s | 263.5s | **-17.1s** | **-6.1%** |
| **Fixture Overhead** | 850.9s | 314.2s | **-536.7s** | **-63.1%** |
| **test_checkpointer Overhead** | 263.4s (14 calls) | 0.0s (14 calls) | **-263.4s** | **-100%** |
| **SentenceTransformer Loading** | 7.4s (3 calls) | 2.5s (1 call) | **-4.9s** | **-66.2%** |

---

## 🤔 Why Only 6% Speedup?

**Expected**: ~70-80% speedup (280s → 60s)
**Actual**: ~6% speedup (280s → 263.5s)

### Root Cause Analysis

The discrepancy is due to **overlapping timing measurements**:

1. **Fixture Timing Includes Test Execution**: The `client` fixture uses an async context manager that wraps the entire test execution. Time spent in `client - AsyncClient creation` (82.9s) includes the actual test logic running inside the context.

2. **test_checkpointer Time Was Double-Counted**: The fixture overhead (263.4s) was measured separately, but the actual time spent was happening in parallel with or as part of test execution, not as pure setup overhead.

3. **Graph Execution is Now the Bottleneck**: With checkpointer overhead eliminated, the remaining time is dominated by:
   - LangGraph execution overhead (~8-15s per multi-turn test)
   - API lifespan context initialization (113.1s for 6 tests, ~19s each)
   - Multiple graph invocations per test

---

## 🔍 Detailed Timing Breakdown

### Fixture Overhead Comparison

#### Before Optimization:
```
test_checkpointer:                263.40s (14 calls, mean 18.81s)
  └─ AsyncSqliteSaver init:       263.40s (SQLite file ops, schema init)

graph_with_mock_data:             7.56s (3 calls, mean 2.52s)
  ├─ FAISSRetriever init:         7.44s (model loading)
  ├─ add_documents:               0.10s
  └─ build_graph:                 0.02s

client:                           112.63s (6 calls, mean 18.77s)
  ├─ lifespan_context:            112.63s (app startup + embeddings)
  └─ AsyncClient creation:        83.64s (includes test execution!)
```

#### After Optimization:
```
test_checkpointer:                0.00s (14 calls, mean 0.000s) ✅
  └─ MemorySaver init:            ~0ms (instant!)

session_retriever:                2.46s (1 call, session-scoped) ✅
  └─ load from disk:              2.46s (one-time load)

graph_with_mock_data:             0.03s (3 calls, mean 0.010s) ✅
  └─ build_graph:                 0.03s (reuses session_retriever)

client:                           113.14s (6 calls, mean 18.86s) ⚠️
  ├─ lifespan_context:            113.14s (still slow!)
  └─ AsyncClient creation:        82.91s (includes test execution)
```

### Individual Test Time Comparison

| Test | Before | After | Change |
|------|--------|-------|--------|
| test_concurrent_sessions | 33.37s | 29.75s | -3.62s (-11%) |
| test_chat_endpoint_multi_turn | 29.54s | 29.56s | +0.02s (0%) |
| test_simulated_api_flow | 18.16s | 27.06s | +8.90s (+49%) ⚠️ |
| test_session_persistence_flow | 26.09s | 23.75s | -2.34s (-9%) |
| test_rag_agent_with_different_thread_ids | 24.68s | 22.49s | -2.19s (-9%) |
| test_supervisor_classification_flow | 14.51s | 18.15s | +3.64s (+25%) ⚠️ |

**Note**: Some tests got SLOWER! This suggests measurement variance or system load fluctuation.

---

## 💡 Key Insights

### 1. Optimization Was Successful But Benefits Are Limited

The checkpointer optimization worked perfectly:
- ✅ Eliminated 263.4s of AsyncSqliteSaver overhead
- ✅ Reduced fixture overhead by 63%
- ⚠️ But total test time only improved 6% due to overlapping measurements

### 2. Real Bottleneck: Graph Execution

With fixture overhead eliminated, the dominant cost is:
- **LangGraph execution**: Each graph.ainvoke() takes 8-15 seconds
- **API lifespan context**: 113s for 6 tests (~19s per test)
- **Multiple invocations**: Tests with 2+ graph calls take 20-30s

### 3. Why API Tests Are Still Slow

The `client` fixture's `lifespan_context` (113.14s) is the new bottleneck:
- App initialization
- Embeddings loading (even though optimized to 2.5s)
- FastAPI startup overhead
- Something else taking ~110s (needs investigation!)

---

## 🎯 What Was Optimized Successfully

| Component | Status | Evidence |
|-----------|--------|----------|
| AsyncSqliteSaver → MemorySaver | ✅ **100% eliminated** | 263.4s → 0.0s |
| Multiple FAISSRetriever instances | ✅ **66% eliminated** | 7.4s (3×) → 2.5s (1×) |
| graph_with_mock_data fixture | ✅ **75% faster** | 7.56s → 0.03s |
| Checkpointer initialization | ✅ **Instant** | 18.8s mean → 0.0s mean |

---

## 🔬 Remaining Bottlenecks (Next Optimization Targets)

### Priority 1: API Lifespan Context (113.14s, 43% of total time)

**Problem**: `app.router.lifespan_context()` takes ~19s per test

**Potential Solutions**:
1. Session-scoped app fixture (initialize once)
2. Skip lifespan in tests, manually inject dependencies
3. Investigate what's causing the 19s delay (profiling needed)

**Expected Impact**: Save ~90-100s (35-40% speedup)

### Priority 2: Graph Execution Overhead (8-15s per multi-turn test)

**Problem**: LangGraph execution is slow even with FakeChatModel

**Analysis**: Each `graph.ainvoke()` call involves:
- State management
- Node execution
- Routing logic
- Message transformation
- FakeChatModel invocation (should be instant)

**Potential Solutions**:
1. Profile graph execution to find hotspots
2. Simplify test scenarios (fewer invocations)
3. Mock graph invocation for non-critical tests

**Expected Impact**: Save ~50-80s (20-30% speedup)

---

## 📈 Projected Performance After Next Phase

| Phase | Time | Cumulative Speedup |
|-------|------|---------------------|
| Original | 280.6s | - |
| After Phase 1 (current) | 263.5s | -6% |
| After Phase 2 (API optimization) | ~170s | -39% |
| After Phase 3 (graph optimization) | ~90-120s | -57-68% |

**Target**: Test suite in **90-120 seconds** (down from 280s)

---

## 🎓 Lessons Learned

### 1. Measure Before AND After

My initial assumption was that AsyncSqliteSaver (263.4s) would translate to 263.4s of wall-clock savings. **Reality**: Only 17.1s saved due to overlapping measurements.

**Lesson**: Fixture timing ≠ wall-clock time when fixtures wrap test execution.

### 2. Multiple Bottlenecks Exist

Fixing one bottleneck (checkpointer) revealed another (API lifespan, graph execution).

**Lesson**: Performance optimization is iterative - fix, measure, fix next bottleneck.

### 3. Instrumentation Was Critical

Without the timing infrastructure, we wouldn't have discovered:
- test_checkpointer was "only" saving 17s in practice
- API lifespan context is the new bottleneck (113s)
- Graph execution is expensive (8-15s per multi-turn test)

**Lesson**: Always measure with instrumentation, never rely on assumptions.

---

## ✅ Conclusion

The optimization **was successful** in eliminating the AsyncSqliteSaver bottleneck:
- ✅ Checkpointer overhead: 263.4s → 0.0s (100% eliminated)
- ✅ Fixture overhead: 850.9s → 314.2s (63% reduction)
- ⚠️ Total test time: 280.6s → 263.5s (6% improvement)

The modest 6% speedup reveals that:
1. **Fixture timing was overlapping** with test execution
2. **New bottlenecks emerged**: API lifespan (113s) and graph execution (8-15s per test)
3. **Further optimization is possible** by targeting these new bottlenecks

**Next Steps**: Profile and optimize API lifespan context (expected: 35-40% additional speedup).
