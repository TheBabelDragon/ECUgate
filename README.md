# ECUgate

**Your agent has the keys. The policy decides which doors open.**

Model-agnostic agent tool and memory substrate for constrained, auditable ECU interaction.

- **Typed tools** — schemas, discovery, structured results
- **Structured memory** — SQLite facts/observations/decisions/outcomes/failures
- **Enforceable permissions** — READ / PROPOSE / EXECUTE
- **Auditable lifecycle** — DISCOVER → … → RECORD
- **Hardware discovery** — ENUMERATE → IDENTIFY → DESCRIBE → VALIDATE (never auto-authorizes writes)
- **Host enumeration** — opt-in serial/USB metadata scan
- **Bench topology** — multi-device inventory, roles, relationships, readiness blockers

**HorsePowerPoint** is the demo app. ECUgate is the product.

**Modular controller platform** (`ecugate.platform`) — vehicle/controller profiles, modular hardware manifests, versioned clone packages with explicit capture completeness, fail-closed compatibility evaluation, and simulated replacement/recovery workflows. ESP32-S3 is a first-class *development* target only; it is not an automotive-qualified ECU. See [docs/MODULAR_CONTROLLER_PLATFORM.md](docs/MODULAR_CONTROLLER_PLATFORM.md).

```bash
python -m ecugate.platform.cli profiles
python -m ecugate.platform.cli esp32-s3
python -m ecugate.platform.cli capture-report
python -m ecugate.platform.cli compatibility --modules esp32-s3-dev-compute-v1
```

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
python -m ecugate.discovery.cli --simulate --manifests manifests/devices
python -m ecugate.discovery.cli --host --manifests manifests/devices
python -m ecugate.discovery.cli --simulate --inventory --save /tmp/bench.json
python -m ecugate.discovery.cli --deps
```

See [docs/HOST_ENUMERATION.md](docs/HOST_ENUMERATION.md) and [docs/BENCH_TOPOLOGY.md](docs/BENCH_TOPOLOGY.md).

## License

MIT
