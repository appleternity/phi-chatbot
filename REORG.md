# Code Reorganization Plan: Remove Legacy Retrieval System

**Date:** 2025-11-06
**Status:** Approved, Ready for Execution
**Context:** Investigation revealed duplicate retrieval systems with runtime type mismatches

---

## Executive Summary

**Problem:** Project has TWO retrieval systems:
- **OLD System** (`app/core/`): PostgreSQLRetriever, HybridRetriever using Document objects
- **NEW System** (`app/retrieval/`): Factory pattern with Simple/Rerank/Advanced strategies using dicts

**Runtime Reality:** Production ONLY uses NEW system. OLD system exists but is NEVER instantiated.

**Type Hint Lie:** Code claims to use `DocumentRetriever` returning `List[Document]`, but actually returns `List[Dict[str, Any]]`. Works due to Python duck typing.

---

## Investigation Findings

### 1. PostgreSQLRetriever - NEVER Instantiated

**Evidence:**
- `app/main.py:132` calls `get_retriever(pool, encoder, reranker)`
- Factory (`app/retrieval/factory.py`) returns: `SimpleRetriever | RerankRetriever | AdvancedRetriever`
- Factory has NO code path creating `PostgreSQLRetriever`
- Zero imports of `postgres_retriever` in production code

**Conclusion:** Defined but never created at runtime.

### 2. Document Dataclass - NEVER Used in Production

**Evidence:**
- NEW retrievers return: `List[Dict[str, Any]]` (see `app/retrieval/simple.py:76-92`)
- RAG agent expects: `list[dict]` (see `app/agents/rag_agent.py:20` - function signature)
- RAG agent uses: `doc.get("chunk_text")` - dict methods, not Document attributes
- Zero imports of `Document` in `app/retrieval/` directory

**Conclusion:** Runtime flow uses plain dicts, not Document objects.

### 3. DocumentRetriever ABC - Type Hints Only

**Evidence:**
- Type hints claim: `retriever: DocumentRetriever`
- Runtime receives: `SimpleRetriever | RerankRetriever | AdvancedRetriever` (NOT subclasses of DocumentRetriever)
- NEW retrievers don't inherit from DocumentRetriever
- Code works because Python doesn't enforce type hints at runtime

**Conclusion:** Type contract mismatch - hints are wrong.

### 4. Parenting Agent - Disabled

**Evidence:**
- `app/config.py:73` - `ENABLE_PARENTING: bool = False`
- Files: `parenting_agent.py`, `parenting_tools.py`, `parenting_state.py` all unused
- Tests: `test_parenting_agent.py` tests disabled feature

**Conclusion:** Dead feature with config flag set to False.

### 5. Hybrid Retrieval - Never Used

**Evidence:**
- Uses FAISS (project uses PostgreSQL + pgvector instead)
- Only referenced by disabled parenting agent
- Test file exists but feature never enabled

**Conclusion:** Abandoned implementation.

---

## Files to Move to deleted/ (17 files)

### Core Legacy Retrieval (5 files)

1. **app/core/retriever.py** - Contains unused `Document` dataclass and `DocumentRetriever` ABC
2. **app/core/postgres_retriever.py** - 492 lines, never instantiated
3. **app/core/hybrid_retriever.py** - 421 lines, FAISS-based (unused)
4. **app/core/reranker.py** - 172 lines, replaced by `qwen3_reranker.py`
5. **app/utils/data_loader.py** - Legacy FAISS data loader

### Parenting Agent (4 files)

6. **app/agents/parenting_agent.py**
7. **app/agents/parenting_tools.py**
8. **app/graph/parenting_state.py**
9. **src/precompute_parenting_embeddings.py**

### Test Files (7 files)

10. **tests/semantic-search/unit/test_postgres_retriever.py**
11. **tests/semantic-search/integration/test_retriever_simplified.py**
12. **tests/unit/test_hybrid_retriever.py**
13. **tests/unit/test_reranker.py**
14. **tests/unit/test_retriever.py**
15. **tests/integration/test_parenting_agent.py**
16. **examples/demo_parenting_fallback.py**

### Documentation (1 file)

17. **docs/PARENTING_AGENT.md**

**Total:** ~2,500 lines of dead code

---

## Files to Update (3 files)

### 1. app/graph/builder.py

**Remove old imports (line 20):**
```python
from app.core.retriever import DocumentRetriever  # DELETE
```

**Add correct imports:**
```python
from app.retrieval import SimpleRetriever, RerankRetriever, AdvancedRetriever  # ADD
```

**Fix type hint (line 77):**
```python
# BEFORE (wrong):
def build_medical_chatbot_graph(
    retriever: DocumentRetriever,
    parenting_retriever: DocumentRetriever | None = None,
    enable_parenting: bool = False,

# AFTER (correct):
def build_medical_chatbot_graph(
    retriever: SimpleRetriever | RerankRetriever | AdvancedRetriever,
    # Remove parenting parameters
```

**Remove parenting node creation (lines 110-120):**
- Delete conditional block that creates parenting agent node
- Remove parenting-related imports if any

### 2. app/agents/rag_agent.py

**Remove old import (line 11):**
```python
from app.core.retriever import DocumentRetriever  # DELETE
```

**Add correct imports:**
```python
from app.retrieval import SimpleRetriever, RerankRetriever, AdvancedRetriever  # ADD
```

**Fix type hint (line 101):**
```python
# BEFORE (wrong):
def create_rag_node(retriever: DocumentRetriever):

# AFTER (correct):
def create_rag_node(retriever: SimpleRetriever | RerankRetriever | AdvancedRetriever):
```

### 3. app/core/__init__.py

**Remove exports (lines 3-4):**
```python
from app.core.retriever import Document, DocumentRetriever  # DELETE BOTH
```

---

## Config Cleanup (1 file)

### app/config.py

**Remove parenting settings (lines 36-37):**
```python
parenting_index_path: str = "data/parenting_faiss_index"  # DELETE
enable_parenting: bool = False  # DELETE
```

**Remove hybrid retrieval settings (lines 58-61):**
```python
dense_weight: float = 0.7  # DELETE
sparse_weight: float = 0.3  # DELETE
reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # DELETE
reranker_top_k: int = 5  # DELETE
```

---

## Execution Steps

### Step 1: Create Directory Structure

```
mkdir -p deleted/app/core
mkdir -p deleted/app/agents
mkdir -p deleted/app/utils
mkdir -p deleted/app/graph
mkdir -p deleted/src
mkdir -p deleted/tests/semantic-search/unit
mkdir -p deleted/tests/semantic-search/integration
mkdir -p deleted/tests/unit
mkdir -p deleted/tests/integration
mkdir -p deleted/examples
mkdir -p deleted/docs
```

### Step 2: Move Files (use mv, not rm)

Move all 17 files listed above to their respective `deleted/` locations.

### Step 3: Update Type Hints

Edit 3 files (builder.py, rag_agent.py, __init__.py) as specified above.

### Step 4: Clean Up Config

Remove 6 lines from config.py as specified above.

### Step 5: Verify

**Check imports work:**
```bash
python -c "from app.main import app; print('✅ Imports OK')"
```

**Check syntax:**
```bash
python -m py_compile app/graph/builder.py
python -m py_compile app/agents/rag_agent.py
python -m py_compile app/core/__init__.py
```

**Check for broken references:**
```bash
grep -r "from app.core.retriever import" app/ --exclude-dir=deleted
grep -r "DocumentRetriever" app/ --exclude-dir=deleted
grep -r "Document(" app/ --exclude-dir=deleted | grep -v "# Document"
```

Should return zero matches (or only type hints in comments).

---

## Expected Impact

### Lines Removed
- **~2,500 lines** moved to deleted/
- Code cleanup removes confusion about which system is active

### Type Safety Improved
- Type hints now match runtime reality
- `SimpleRetriever | RerankRetriever | AdvancedRetriever` accurately describes factory return

### Architecture Clarified
- One retrieval system: `app/retrieval/` (factory-based)
- Clear separation: retrieval strategies vs. legacy implementations

### Risk Assessment
- **Risk: LOW** - All deleted code provably unused at runtime
- **Testing: Integration tests** should still pass (they use NEW system)
- **Rollback: Easy** - All code moved to deleted/, not removed

---

## Why This is Safe

1. **Runtime Verification:** Traced actual execution path from startup → factory → retrieval
2. **Zero Instantiation:** grep confirms no production code creates deleted classes
3. **Type Mismatch Works:** Python duck typing allows dicts where Documents expected
4. **Tests Use NEW System:** Integration tests already test Simple/Rerank/Advanced retrievers
5. **Config Confirms:** ENABLE_PARENTING=False proves parenting code is dead

---

## Architecture After Cleanup

### What Remains (Active Production Code)

```
app/
├── retrieval/              # ✅ NEW SYSTEM (Active)
│   ├── factory.py          # Strategy factory
│   ├── base.py             # RetrieverProtocol
│   ├── simple.py           # Vector search only
│   ├── rerank.py           # Vector + reranking
│   └── advanced.py         # Query expansion + reranking
│
├── core/
│   └── qwen3_reranker.py   # ✅ Active reranker
│
├── agents/
│   └── rag_agent.py        # ✅ Active RAG agent
│
└── graph/
    └── builder.py          # ✅ Active graph builder
```

### What's Deleted (Moved to deleted/)

```
deleted/
├── app/core/
│   ├── retriever.py        # ❌ Legacy: Document, DocumentRetriever
│   ├── postgres_retriever.py  # ❌ Never instantiated
│   ├── hybrid_retriever.py    # ❌ FAISS-based
│   └── reranker.py         # ❌ Replaced by qwen3
│
├── app/agents/
│   ├── parenting_agent.py  # ❌ ENABLE_PARENTING=False
│   └── parenting_tools.py  # ❌ Parenting disabled
│
└── tests/                  # ❌ Tests for deleted code
    └── ...
```

---

## Questions & Answers

**Q: Why not just delete instead of moving to deleted/?**
A: Preserves code for reference if needed. Easy rollback. Can delete deleted/ later after confirming.

**Q: Will this break tests?**
A: Tests that depend on deleted code will fail. Move those tests to deleted/ too. Integration tests using NEW system should pass.

**Q: What if we need PostgreSQLRetriever later?**
A: It still exists in deleted/ and can be restored. But current NEW system (SimpleRetriever) does the same thing better.

**Q: Why keep qwen3_reranker.py but delete reranker.py?**
A: qwen3_reranker.py is actively used by RerankRetriever and AdvancedRetriever in production.

**Q: Are type hints important if Python doesn't enforce them?**
A: Yes - IDEs use them for autocomplete, mypy can check them, they document expected types. Should be accurate.

---

## Related Contexts

**SSE Streaming (Current Work):**
- This cleanup is orthogonal to SSE streaming feature
- Can be done before/after/during streaming work
- No conflicts expected

**Testing Strategy:**
- Run existing integration tests after cleanup
- They already test NEW retrieval system
- Deleted tests were testing legacy code

**Future Work:**
- After cleanup, consider adding strict mypy type checking
- Could add Protocol-based typing for better flexibility

---

**End of Document**
