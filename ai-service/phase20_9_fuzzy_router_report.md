# Phase 20.9 — Hybrid Fuzzy Intent Router Report

## 1. Executive Summary
Phase 20.9 successfully implements a lightweight, deterministic, CPU-friendly **Hybrid Fuzzy Intent Router** for the Shared AI Service. The system now understands typo variations, informal Indonesian abbreviations, slang, repeated character elongation, and paraphrased user questions without relying on LLM/Qwen calls for intent classification.

- **Total Baseline Tests**: 211 / 211 PASS
- **New Phase 20.9 Tests**: 39 / 39 PASS
- **Total Regressions**: **250 / 250 PASS (100%)**
- **Benchmark Accuracy**: **100.00%** on 50-prompt multi-domain dataset
- **False Positive Rate**: **0.00%**
- **False Negative Rate**: **0.00%**
- **Average Router Latency**: **0.83 ms** (Target: < 10 ms)
- **P95 Router Latency**: **3.57 ms** (Target: < 15 ms)
- **Infrastructure Impact**: 0 new containers, 0 new models, 0 embedding calls for routing.

---

## 2. Routing Architecture: Exact Priority with Fuzzy Fallback

The routing pipeline follows a strict hierarchical evaluation:

```
                  ┌───────────────────────────────┐
                  │          User Input           │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │      Text Normalization       │
                  │ (Slang, Repetition, Accents)  │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                  ┌───────────────────────────────┐
                  │ 1. Exact / Regex / Keyword    │
                  │    Deterministic Pass         │
                  └───────────────┬───────────────┘
                                  │
                   Confident Match?
                    ├── YES ──► Output Domain Intent & Candidate Tools
                    └── NO
                          │
                          ▼
                  ┌───────────────────────────────┐
                  │ 2. Hybrid Fuzzy Matcher       │
                  │    (Pre-indexed Phrases)      │
                  └───────────────┬───────────────┘
                                  │
                   Confident & Unambiguous?
                    ├── YES ──► Output Fuzzy Intent & Mapped Tools
                    └── NO
                          │
                          ▼
                  ┌───────────────────────────────┐
                  │ 3. GENERAL_CHAT Fallback      │
                  │    (Mode B: 0 Tools, 0 RAG)   │
                  └───────────────────────────────┘
```

1. **Pre-processing / Normalization**: Lowercases, deduplicates repeated characters, expands chat abbreviations, and tokenizes cleanly.
2. **First Priority: Exact / Regex Matching**: High-confidence keyword and regex checks execute in sub-millisecond time.
3. **Second Priority: Hybrid Fuzzy Matcher**: Triggered only when exact matching produces no domain tools. Evaluates token set coverage, sliding n-gram windows, and `SequenceMatcher` typo ratios.
4. **Third Priority: Ambiguity & Low-Confidence Guard**: If top score < 0.78 or top two intent scores differ by < 0.08, the system safely falls back to `GENERAL_CHAT` (no tools, no private vector queries).

---

## 3. Normalization Strategy (`app/agent/normalizer.py`)

The `IntentNormalizer` layer handles typical natural Indonesian chat variations:
- **Character Elongation**: Collapses repeated consecutive characters (`"halooo"` $\to$ `"halo"`, `"progrrrres"` $\to$ `"progres"`, `"yessss"` $\to$ `"yes"`).
- **Abbreviation & Contraction Expansion**:
  - `"brp"` $\to$ `"berapa"`, `"bljr"` $\to$ `"belajar"`, `"sy"` / `"gw"` $\to$ `"saya"`
  - `"gmn"` / `"bgm"` $\to$ `"bagaimana"`, `"sdh"` / `"udh"` $\to$ `"sudah"`
  - `"rekom"` / `"rekomendasiin"` $\to$ `"rekomendasi"`
  - `"vidio"` / `"vdo"` $\to$ `"video"`, `"dok"` $\to$ `"dokumen"`
  - `"assestment"` / `"asesment"` $\to$ `"assessment"`, `"profle"` $\to$ `"profile"`
  - `"transkip"` $\to$ `"transkrip"`
- **Pluralization Suffixes**: `"modul2"` $\to$ `"modul modul"`, `"soal2"` $\to$ `"soal soal"`.
- **Disruptive Punctuation Trimming**: Strips trailing punctuation (`?`, `!`, `.`) while preserving token boundaries.

---

## 4. Similarity Algorithm & Thresholds (`app/agent/fuzzy_matcher.py`)

The `FuzzyIntentMatcher` combines:
1. **Exact String Match**: `query == phrase` $\to$ Score: 1.0.
2. **Exact Token Set Containment**: All tokens of phrase present in query tokens $\to$ Score: 0.95–1.0.
3. **Sliding N-Gram Window**: Compares contiguous $k$-token windows of the query against reference phrases using `difflib.SequenceMatcher`.
4. **Fuzzy Token Matching**: Per-token typo similarity ($\ge 0.80$) weighted by token coverage.
5. **Thresholds**:
   - `HIGH_CONFIDENCE_THRESHOLD = 0.78`: Prompts with score $\ge 0.78$ are eligible for intent acceptance.
   - `AMBIGUITY_MARGIN = 0.08`: If $(\text{top\_score} - \text{second\_top\_score}) < 0.08$ and both are near threshold, the request is flagged as ambiguous and routed to `GENERAL_CHAT`.

---

## 5. Critical False Positive Safeguards

- **"profile" vs "file" Protection**:
  - `_matches_any_keyword` uses regex word boundaries `(?:\b|\A)kw(?:\b|\Z)` to prevent substring matches (e.g., `"file"` matching inside `"profile"`).
  - Standalone `"file"` keyword requires PDF/safety/SOP context (`"pdf"`, `"dokumen"`, `"sop"`, `"k3"`, `"apd"`) before triggering `PDF_KNOWLEDGE`.
  - Prompts like `"profile saya"` or `"learning profile"` route strictly to `LMS_PROFILE` and **never** to `PDF_KNOWLEDGE`.
- **Conversational & Casual Insulation**:
  - Non-LMS casual prompts (`"halo"`, `"selamat malam"`, `"buatkan resep ayam"`, `"apa itu AI?"`, `"jelaskan Docker"`) achieve maximum domain fuzzy scores $< 0.40$ and route strictly to `GENERAL_CHAT`.

---

## 6. Benchmark Results

A dedicated 50-prompt benchmark dataset covering all canonical intents was evaluated (`tests/test_phase20_9_fuzzy_router.py::test_benchmark_dataset_accuracy_and_metrics`):

| Metric | Target | Result | Status |
|---|---|---|---|
| **Total Benchmark Prompts** | $\ge 50$ | 50 prompts | PASS |
| **Intent Classification Accuracy** | $\ge 90.0\%$ | **100.00%** | PASS |
| **False Positive Rate** | $0.0\%$ | **0.00%** | PASS |
| **False Negative Rate** | $0.0\%$ | **0.00%** | PASS |
| **GENERAL_CHAT Accuracy** | $100.0\%$ | **100.00%** | PASS |
| **Average Router Latency** | $< 10.0\text{ ms}$ | **0.828 ms** | PASS |
| **P95 Router Latency** | $< 15.0\text{ ms}$ | **3.569 ms** | PASS |

### Comparison: Fuzzy Router vs Qwen LLM Routing

| Feature | Qwen LLM Routing | Hybrid Fuzzy Intent Router | Improvement |
|---|---|---|---|
| **Routing Latency** | ~400–1200 ms | **0.83 ms** | **~500x – 1400x faster** |
| **CPU / GPU Load** | High VRAM/Compute | **Negligible CPU (<1%)** | **Near zero overhead** |
| **Cost per Request** | LLM Token Ingestion | **0 Tokens** | **100% Free** |
| **Determinism** | Stochastic | **100% Deterministic** | **Consistent routing** |
| **Failure Mode** | Network / GPU crash | **Graceful in-memory fallback** | **Robust** |

---

## 7. Security & Tenant Isolation Boundary

- **Intent Prediction Isolation**: Fuzzy matching **only** determines `AgentIntent` and candidate tool names.
- **Strict Boundary**: Fuzzy router **never** determines or overrides `user_id`, `application` (tenant), `role`, JWT credentials, API keys, or permissions.
- **Tenant Enforcement**:
  - Public Chat requests (`application="public-chat"`) cannot invoke private OWL LMS tools (`get_learning_progress`, `get_user_learning_profile`, `get_user_assessments`, `get_learning_recommendations`, `search_pdf_knowledge`) even if a fuzzy intent is classified.
  - `ToolAuthorizationService.validate_tenant_access` and `AgentOrchestrator` enforce tenant checks at execution time.
  - Cross-user data isolation is strictly preserved (`validate_user_access`).

---

## 8. Full Regression Suite Results

Execution of full pytest suite across all modules:
```
================ 250 passed, 434 warnings in 452.61s (0:07:32) =================
```
All existing tests across Agent, MCP Tools, RAG, Video, PDF, Public Chat, HR Corner, OWL, Security, Observability, and Gateway continue to pass without any regressions.

---

## 9. Conclusion
Phase 20.9 is fully implemented, verified, tested, committed, and deployed on `main`. The Shared AI Service now features sub-millisecond, typo-resilient, Indonesian-natural intent routing with 0 false positives, 100% test pass rate, and zero added infrastructure.
