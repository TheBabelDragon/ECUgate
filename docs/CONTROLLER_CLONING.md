# Controller Cloning & Capture Completeness

## Clone package (`clone_package.v1`)

A versioned, deterministic backup package with:

- `controller_identity` / `hardware_identity`
- Independent regions: firmware, calibration, configuration, diagnostic metadata, other
- `compatibility_constraints`, `provenance`, `recovery_requirements`
- SHA-256 `package_digest` over canonical content

## Region status

Each region has an explicit status:

| Status | Meaning |
|--------|---------|
| `captured` | Data obtained and (when applicable) digested |
| `protected` | Region exists but is security-protected; not extracted |
| `unsupported` | Capture method not available for this controller |
| `unreadable` | Attempt failed or media unreadable |
| `not_attempted` | Capture not tried |

**Never** report a complete clone merely because a firmware binary was copied.

## Completeness

`ClonePackage.capture_completeness()` reports lists per status and `is_complete` only when all registered regions are `captured` and required kinds succeeded.

Protected, unsupported, unreadable and not_attempted regions **prevent** completeness.

## Protected material

Immobilizer secrets, cryptographic keys and credentials are **not** extracted. They appear as `status: protected` and `protected_dependency_ref` only.

## Integrity

Deterministic canonical JSON, SHA-256 package digest, `verify_integrity()`.
