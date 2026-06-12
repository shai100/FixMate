# Build-log documentation rule + retroactive phase docs

**Commit:** (this commit) — `docs: per-commit build log rule + phase 0/1 build logs`
**Plan:** n/a — process change requested by Shai
**Date:** 2026-06-12

## What was built

- **`docs/phase-0-compose-infrastructure.md`** and **`docs/phase-1-schema-rls.md`** — retroactive build-log docs for the two completed phases, each with "What was built" and "Verification evidence" sections.
- **`CLAUDE.md` §4.7 (Commit Documentation / Build Log)** — new rule: every commit Claude creates ships with a companion markdown file in `docs/` (`phase-N-<name>.md` for plan phases, `<yyyy-mm-dd>-<slug>.md` otherwise) containing the commit header, what was built, and pasted verification evidence. Revision-history row added.

## Verification evidence

Docs-only change — no code paths affected. Verified `pytest tests/db -v` still green before committing (8 passed); the three new docs and the CLAUDE.md section render as valid markdown.
