# Quickstart

```bash
git clone https://github.com/TheBabelDragon/ECUgate.git
cd ECUgate
pip install -e ".[dev]"
pytest
python -m examples.horsepowerpoint.demo
```

## Discovery CLI

```bash
python -m ecugate.discovery.cli --simulate --manifests manifests/devices
python -m ecugate.discovery.cli --host --manifests manifests/devices
```

Host enumeration is opt-in and non-destructive. Discovery never sets `authorized: true`.

See [HOST_ENUMERATION.md](HOST_ENUMERATION.md) for platform notes.

## Bench inventory

```bash
python -m ecugate.discovery.cli --simulate --inventory --manifests manifests/devices --save /tmp/bench.json
```

Multi-device topology and readiness blockers: [BENCH_TOPOLOGY.md](BENCH_TOPOLOGY.md).
