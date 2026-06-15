# Phase 9 — Keycloak OIDC (replace dev auth)

**Commit:** `927af6e` — `feat: Keycloak OIDC auth — JWKS Bearer validation + realm bootstrap (phase 9)`
**Plan:** `docs/superpowers/plans/2026-06-12-fixmate-mvp.md` §Phase 9 (Appendix A.6; CLAUDE.md §3 Auth, §6)
**Date:** 2026-06-15

---

## What was built

Real OIDC authentication that replaces the spoofable dev-auth headers (Phase 6) when
`DEV_AUTH=false`. Bearer JWTs are validated against the Keycloak realm's published JWKS and
mapped to the **same `AuthContext` dataclass** the API already depends on (Appendix A.6), so
no handler changed — only the source of identity did.

### Files

- **`fixmate/api/auth_oidc.py`** — the OIDC validator.
  - `decode_token(token, key, *, issuer, audience, verify_audience)` — verifies signature
    (RS256), expiry, and issuer with a known public key, then maps claims. Split out from
    JWKS fetching so it is unit-testable with a locally generated keypair (no live Keycloak).
  - `claims_to_context(claims)` — pure mapping; raises `jwt.InvalidTokenError` when the
    `organization_id` claim, `sub`, or a FixMate role is missing. A token without tenancy or
    role must never reach business logic (CLAUDE.md §6).
  - Role resolution grants the **highest-privilege** FixMate realm role present
    (`admin > curator > tech`), ignoring Keycloak's default roles (`offline_access`, etc.).
  - `OIDCValidator` wraps `PyJWKClient` (caches signing keys; picks up rotation on cache
    miss) so the realm public key is resolved without a per-request network round-trip.
  - `get_validator()` builds the validator from settings (issuer/jwks_uri derived from
    `keycloak_base_url` + `keycloak_realm`), `lru_cache`d.
- **`fixmate/api/deps.py`** — `get_current_user` now switches on `DEV_AUTH`: header auth when
  true, `_oidc_auth(authorization)` when false (reads `Authorization: Bearer …`, validates,
  converts `jwt.InvalidTokenError` → HTTP 401). The Phase 6 placeholder 501 is gone.
- **`fixmate/core/settings.py`** — `keycloak_base_url`, `keycloak_realm`, `oidc_client_id`,
  `oidc_verify_audience`.
- **`scripts/keycloak_bootstrap.py`** — idempotent realm provisioner. Creates realm `fixmate`,
  enables the **unmanaged-attribute policy** (Keycloak 26 drops undeclared attributes
  otherwise — this was the gotcha that silently stripped `organization_id` from tokens), a
  public `fixmate-api` client with direct-access grants, an `organization_id` attribute →
  claim mapper, roles `tech`/`curator`/`admin`, and one test user per role (with first/last
  name + cleared required-actions so the password grant isn't blocked by "Verify Profile").
- **`tests/auth/test_oidc.py`** — 10 unit tests + 1 live integration test (see evidence).
- **`pyproject.toml`** — added `pyjwt[crypto]` (RS256 verification needs `cryptography`).
- **`.env.example`, `setup-instructions.md`** — new OIDC env vars + a Phase 9 auth section.

### Contracts upheld

- **Appendix A.6** — `AuthContext(org_id, user_id, role)` produced by dev auth (6) and OIDC
  (9) interchangeably; handlers are backend-agnostic.
- **CLAUDE.md §6** — org id comes from the verified token claim, never a query param; tokens
  without an org claim are rejected.

---

## Verification evidence

### Unit tests (no Keycloak required)

```
$ python -m pytest tests/auth -v -m "not integration"
tests/auth/test_oidc.py::test_valid_token_maps_to_auth_context PASSED
tests/auth/test_oidc.py::test_role_claim_maps_highest_privilege PASSED
tests/auth/test_oidc.py::test_missing_org_claim_rejected PASSED
tests/auth/test_oidc.py::test_no_fixmate_role_rejected PASSED
tests/auth/test_oidc.py::test_expired_token_rejected PASSED
tests/auth/test_oidc.py::test_garbage_token_rejected PASSED
tests/auth/test_oidc.py::test_wrong_signing_key_rejected PASSED
tests/auth/test_oidc.py::test_wrong_issuer_rejected PASSED
tests/auth/test_oidc.py::test_claims_to_context_pure PASSED
tests/auth/test_oidc.py::test_oidc_branch_rejects_missing_bearer PASSED
9 passed (+ test_auth.py existing dev-auth tests still green)
```

### Live integration — real password-grant flow against Keycloak

```
$ docker compose --profile auth up -d keycloak
$ python scripts/keycloak_bootstrap.py
created realm 'fixmate'
enabled unmanaged attributes
created client 'fixmate-api'
  created org-id mapper
created role 'tech' / 'curator' / 'admin'
created user 'tech@example.com' / 'curator@example.com' / 'admin@example.com'
Done. Realm 'fixmate', client 'fixmate-api', demo org 00000000-0000-0000-0000-0000000000d0

$ python -m pytest tests/auth -v   # includes integration
tests/auth/test_oidc.py::test_password_grant_flow_against_live_keycloak PASSED
11 passed in 1.14s
```

The integration test fetches a real access token from Keycloak via the password grant, runs
it through `get_validator().validate(...)`, and asserts the resulting `AuthContext` has
`role == "tech"` and a UUID `org_id` — proving the full sign → JWKS → verify → map chain.

### Full non-integration suite (no regressions)

```
$ python -m pytest -m "not integration" -q
63 passed, 31 deselected in 31.61s

$ ruff check fixmate/api/auth_oidc.py fixmate/api/deps.py scripts/keycloak_bootstrap.py tests/auth/
All checks passed!
```
