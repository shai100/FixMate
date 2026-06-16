# Full Teaching-Level Code Documentation

**Date:** 2026-06-16
**Plan:** Add full documentation to all code files (teaching-level docstrings, document everything)
**Related guidance:** CLAUDE.md §4.4 (rewritten in this change), §4.7 (build log), §4.9 (architecture doc)

---

## What was built

Added in-file documentation across the **entire** codebase so a developer new to
FixMate (and to the troubleshooting-RAG domain) can understand each file without
prior context. This is documentation-only: no runtime behavior, signatures,
imports, or logic changed.

### Documentation standard applied
- **Python:** module docstring on every `.py` (one-liner on `__init__.py`
  package markers); class docstring on every class (purpose, key fields,
  invariants); function docstring on public functions (summary + Args/Returns/
  Raises where useful + a plain-language "how it works" note for non-trivial
  units). Existing inline comments preserved; new ones added only for non-obvious
  logic.
- **TypeScript/React:** file-header doc-comment on every `.ts`/`.tsx`; doc-comment
  on every exported component, function, hook, and type/interface; short
  "how it works" notes on stateful components (state machines in `FeedbackBar`,
  `ReviewDetail`; parsing in `AnswerCard`).
- **Config:** comments on non-default choices in `docker-compose.yml`,
  `pyproject.toml`, `web/vite.config.ts`, `web/eslint.config.js`,
  `web/index.html`. JSON configs (`tsconfig.json`, `package.json`) can't hold
  comments, so they're documented in `docs/ARCHITECTURE.md` §9.

### Areas covered
- **Backend** (`fixmate/`): `core` (settings, models — all 15 ORM tables, db,
  storage), `api` (main, deps, auth_oidc, schemas — 30+ models, all 8 routers),
  `answers` (composer + RAG pipeline, confidence, groundedness, prompts, logs,
  cli), `retrieval` (service, vector, keyword, rerank, fusion, cli), `llm` (base
  protocol, factory, both providers, embeddings, cli), `ingestion` (pipeline,
  pdf, chunking, figures, registry, tasks, cli), `curation` (service, prescreen,
  states), `feedback`, `evals` (run, fixtures), and every `__init__.py`.
- **Database & scripts:** `db/migrations/env.py` + the two migrations,
  `scripts/healthcheck.py`, `scripts/seed_demo.py`, `scripts/keycloak_bootstrap.py`.
- **Frontend** (`web/src/`): `main.tsx`, `App.tsx`, `api.ts`, `auth.ts`,
  `types.ts`; all components (Shell, Icon, DevLogin, EquipmentPicker, ChatView,
  AnswerCard, EscalationCard, FeedbackBar, FixSubmitForm, Console, ReviewQueue,
  ReviewDetail, FixesAdmin, DocumentsAdmin, EquipmentAdmin, UsersAdmin) and
  screens (Packs, Profile, Settings); all 6 test files + `test/setup.ts`.
- **Standard codified:** CLAUDE.md §4.4 rewritten (documentation is now the
  default), §12 revision row added, ARCHITECTURE.md §9 note for JSON configs.

---

## Verification evidence

### Python byte-compile (docstring syntax valid)
```
$ python -c "import compileall,sys; ok=compileall.compile_dir('fixmate', quiet=1) and compileall.compile_dir('scripts', quiet=1) and compileall.compile_dir('db', quiet=1); sys.exit(0 if ok else 1)" && echo PYCOMPILE_OK
PYCOMPILE_OK
```

### Frontend build (tsc + Vite)
```
$ npm run build
> tsc -b && vite build
vite v5.4.21 building for production...
✓ 52 modules transformed.
✓ built in 1.06s
PWA v0.20.5 ... files generated
```

### Lint (zero-warnings policy)
```
$ npm run lint
> eslint . --max-warnings 0
(no output — clean)
```

### Frontend tests (Vitest)
```
$ npm test
 Test Files  6 passed (6)
      Tests  16 passed (16)
```

### Backend tests
```
$ python -m pytest --co -q
123 tests collected in 3.65s

$ python -m pytest -m "not integration" -q
85 passed, 38 deselected in 32.23s
```
(38 integration tests deselected — they require the Docker Compose services running.)
