# Today Task Plan: Missing & Weak Areas

Date: 2026-04-02
Owner: Dev Session

This document is the working checklist for today. It captures the highest-value weaknesses found during repo audit so we can execute in order.

---

## 1) API Generator outputs scaffold-only handlers (Missing behavior)

**Status:** Missing implementation depth  
**Priority:** P0

### Evidence
- `src/tools/api_generator.py` currently emits route functions with:
  - `# TODO: implement`
  - `raise NotImplementedError(...)`

### Why this is weak
- Generated API code looks complete but cannot run real business logic.
- Reduces trust in "generator" workflows for production usage.

### Today action
- Add configurable generation modes:
  - `stub` (current behavior)
  - `passthrough` (calls source function/service if importable)
  - `mock` (returns deterministic sample payloads)
- Add tests proving generated code is runnable in non-stub modes.

### Done criteria
- Generated routes no longer default to hard NotImplemented-only behavior.
- Tests verify at least one non-stub strategy works end-to-end.

---

## 2) Silent exception handling across tools (Weak observability)

**Status:** Weak reliability diagnostics  
**Priority:** P0

### Evidence
- Broad `except Exception: pass` patterns found in:
  - `src/tools/chat_engine.py`
  - `src/tools/doc_fetcher.py`
  - `src/tools/self_builder.py`
  - `src/tools/agent_memory.py`
  - `src/tools/prompt_lab.py`

### Why this is weak
- Failures are hidden and hard to debug.
- System may degrade silently without operator visibility.

### Today action
- Replace silent `pass` with lightweight structured warning logging.
- Preserve non-blocking behavior, but record context (tool, function, error type).
- Add targeted tests asserting expected fallback + logged warning paths.

### Done criteria
- No silent broad exception swallowing in critical paths.
- Failures are discoverable in logs/audit output without crashing flows.

---

## 3) Coverage analyzer emits placeholder assertions (Weak output quality)

**Status:** Weak generated test quality  
**Priority:** P1

### Evidence
- Placeholder output strings include TODO markers such as:
  - `assert result is not None  # TODO: add real assertion`
  - boundary/error TODO comments
  - unresolved parameter examples (`???`)

### Why this is weak
- Generated tests are not directly useful and require manual rewriting.
- Weakens confidence in test-assist features.

### Today action
- Improve heuristics for assertion generation from return types and names.
- Replace unresolved placeholders with safe defaults or explicit skip markers.
- Add tests for generated output quality floor.

### Done criteria
- Output contains actionable tests with minimal placeholders.
- Added/updated tests enforce no low-value template regressions.

---

## 4) Project metadata still placeholder-level (Missing release hygiene)

**Status:** Missing polish/governance detail  
**Priority:** P2

### Evidence
- `pyproject.toml` still contains generic author placeholder values.

### Why this is weak
- Reduces package/release professionalism.
- Causes avoidable cleanup before publishing/distribution.

### Today action
- Update package metadata to real maintainer/project identity.
- Align versioning notes with release workflow expectations.

### Done criteria
- Metadata is publish-ready and no placeholder identity fields remain.

---

## Recommended Execution Order (Today)

1. P0: API generator behavior upgrade
2. P0: Exception observability hardening
3. P1: Coverage analyzer output quality
4. P2: Metadata cleanup

---

## Session Checklist

- [x] Implement API generator non-stub mode(s)
- [x] Add/adjust tests for API generator behavior
- [x] Replace silent exception swallowing with warning logging
- [x] Add tests for fallback-with-logging behavior
- [ ] Improve generated test assertion quality
- [ ] Add tests for coverage analyzer output quality
- [ ] Clean pyproject metadata placeholders
- [x] Run `pytest -q`
- [x] Run extension compile check

---

## Notes

- Existing baseline is healthy (`pytest` and extension compile pass).
- This plan focuses on raising trust and production-readiness rather than adding new surface area.

---

## Live Mode Follow-Through (Implemented)

- [x] Add continuous `live` CLI mode for learning-only cycles
- [x] Persist live state and cycle history for future sessions
- [x] Add unlockable slice model (`learn`, `research`, `optimize`)
- [x] Keep default live execution limited to `learn`
- [x] Validate via real CLI run (`live status`, bounded `live --iterations 1`)