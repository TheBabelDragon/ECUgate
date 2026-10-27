# ECUgate

**Your agent has the keys. The policy decides which doors open.**

Model-agnostic agent tool and memory substrate for constrained, auditable ECU interaction.

- **Typed tools** — schemas, discovery, structured results
- **Structured memory** — SQLite facts/observations/decisions/outcomes/failures
- **Enforceable permissions** — READ / PROPOSE / EXECUTE
- **Auditable lifecycle** — DISCOVER → READ → RECALL → PROPOSE → VALIDATE → AUTHORIZE → EXECUTE → OBSERVE → RECORD
- **Hardware discovery** — ENUMERATE → IDENTIFY → DESCRIBE → VALIDATE (never auto-authorizes writes)
- **Host enumeration** — opt-in serial/USB metadata scan; simulation remains the default

**HorsePowerPoint** is the demo app. ECUgate is the product.

## Quick start

```bash
git clone https://github.com/TheBabelDragon/ECUgate.git
cd ECUgate
pip install -e ".[dev]"
pytest
python -m examples.horsepowerpoint.demo
```

### Discovery CLI

```bash
# Simulated interface (default, no hardware)
python -m ecugate.discovery.cli --simulate --manifests manifests/devices

# Opt-in host serial/USB enumeration (non-destructive)
python -m ecugate.discovery.cli --host --manifests manifests/devices

# Optional dependency status
python -m ecugate.discovery.cli --deps
```

Host extras (optional): `pip install -e ".[host]"` for pyserial/pyusb. See [docs/HOST_ENUMERATION.md](docs/HOST_ENUMERATION.md).

## Product surface

- Typed tools + permissions (READ / PROPOSE / EXECUTE)
- Structured SQLite memory (never used as authorization)
- Auditable lifecycle with explicit authorize boundary
- Schema-driven discovery (simulator + optional host enumerator)
- HorsePowerPoint demo (simulated ECU only — no real vehicle I/O)

## License

MIT
