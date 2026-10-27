# ECUgate

**Your agent has the keys. The policy decides which doors open.**

Model-agnostic agent tool and memory substrate for constrained, auditable ECU interaction.

## ⚠️ Implementation is on `feat/ecugate-core`

`main` is not the working tree yet. Use:

```bash
git clone https://github.com/TheBabelDragon/ECUgate.git
cd ECUgate
git checkout feat/ecugate-core
pip install -e ".[dev]"
pytest
python -m examples.horsepowerpoint.demo
```

Branch: https://github.com/TheBabelDragon/ECUgate/tree/feat/ecugate-core

## Product

- Typed tools + permissions (READ / PROPOSE / EXECUTE)
- Structured SQLite memory (never used as authorization)
- Auditable lifecycle: DISCOVER → READ → RECALL → PROPOSE → VALIDATE → AUTHORIZE → EXECUTE → OBSERVE → RECORD
- Schema-driven hardware discovery (simulation-first; discovery never authorizes writes)
- HorsePowerPoint demo (simulated ECU only — no real vehicle I/O)

## License

MIT
