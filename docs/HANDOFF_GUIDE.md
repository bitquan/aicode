# Handoff Guide

## Purpose

Use this guide when handing `coding-ai-app` work to:

- another human developer
- another AI assistant
- future you after a break

Good handoff is part of the product. If the next person cannot quickly understand state, risk, and next steps, the work is not really done.

## Start Here

Before continuing work, read in this order:

1. `README.md`
2. `ROADMAP.md`
3. `docs/DEV_BOOK.md`
4. `docs/MAINTAINER_PLAYBOOK.md`
5. `docs/COMMAND_BOOK.md`
6. `docs/SELF_IMPROVEMENT_BASELINE_PACK_V1.md`

## What Every Handoff Should Answer

- what changed
- why it changed
- what was verified
- what is still risky
- what remains next
- which docs were updated

## Minimal Handoff Checklist

- branch or commit is identified
- tree is clean, or dirty files are called out explicitly
- verification commands and results are recorded
- runtime assumptions are stated
- extension version or VSIX version is stated when relevant
- open questions are listed

## Current Repo Truth to Preserve

When handing off, keep these truths explicit:

- the repo is aiming for strong AI dev assistant parity, not just chat UI polish
- self-improvement is supervised and gated
- research-first routing is required for feature work
- runtime truth matters as much as feature output
- extension packaging/install integrity matters because stale installs can mislead debugging

## Recommended Handoff Format

### Summary

- one short paragraph on the change

### Files

- list the important files touched

### Verification

- exact commands run
- high-signal result

### Risks

- what still looks fragile

### Next Step

- one or two recommended next actions

## Dirty Tree Rules

If the tree is not clean:

- separate unrelated work before handoff if possible
- never imply the tree is clean when it is not
- name the dirty files and why they are dirty
- do not bury risky local-only edits inside a vague summary

## Extension-Specific Handoff

If the VS Code extension changed, include:

- installed extension version
- packaged VSIX path
- whether `verify:vsix` passed
- whether the panel/runtime UI was rechecked after reload

## Self-Improvement Handoff

If self-improvement logic changed, include:

- current mode
- current baseline level
- whether apply is still supervised
- latest readiness or acceptance result
- whether rollback and allowlists were re-verified

## Docs Sync Handoff

If behavior changed, say which docs were updated:

- `README.md`
- `ROADMAP.md`
- `.github/copilot-instructions.md`
- `docs/DEV_BOOK.md`
- `docs/MAINTAINER_PLAYBOOK.md`
- `docs/COMMAND_BOOK.md`

## Final Rule

Handoff should reduce mystery, not move mystery downstream.
