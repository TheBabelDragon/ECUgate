# ECUgate

**Your agent has the keys. The policy decides which doors open.**

Model-agnostic agent tool and memory substrate for constrained, auditable ECU interaction.

- **Typed tools** — schemas, discovery, structured results
- **Structured memory** — SQLite facts/observations/decisions/outcomes/failures
- **Enforceable permissions** — READ / PROPOSE / EXECUTE
- **Auditable lifecycle** — DISCOVER → READ → RECALL → PROPOSE → VALIDATE → AUTHORIZE → EXECUTE → OBSERVE → RECORD
- **Hardware discovery** — ENUMERATE → IDENTIFY → DESCRIBE → VALIDATE (never auto-authorizes writes)

**HorsePowerPoint** is the demo app. ECUgate is the product.

## Quick start

```bash
git clone https://github.com/TheBabelDragon/ECUgate.git
cd ECUgate
git checkout feat/ecugate-core   # until PR #1 merges
pip install -e ".[dev]"
pytest
python -m examples.horsepowerpoint.demo
```

## Product surface

- Typed tools + permissions (READ / PROPOSE / EXECUTE)
- Structured SQLite memory (never used as authorization)
- Auditable lifecycle with explicit authorize boundary
- Schema-driven hardware discovery (simulation-first)
- HorsePowerPoint demo (simulated ECU only — no real vehicle I/O)

## License

MIT
