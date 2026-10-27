# Quickstart

```bash
git clone https://github.com/TheBabelDragon/ECUgate.git
cd ECUgate
git checkout feat/ecugate-core
pip install -e ".[dev]"
pytest
python -m examples.horsepowerpoint.demo
python -m examples.horsepowerpoint.demo --db /tmp/hpp.db --reject-first
```

Discovery demo (simulated device):

```python
from ecugate.discovery import DiscoveryEngine
from ecugate.discovery.pipeline import InterfaceRecord
from ecugate.discovery.manifests import load_manifests

eng = DiscoveryEngine(manifest_dir="manifests/devices")
eng.inject_simulated_interface(InterfaceRecord(
    interface_id="sim0", interface_type="simulated",
    vendor_id="SIMU", product_id="ECU1",
    metadata={"device_id": "sim.ecu.v1"},
))
print(eng.discover().to_json())
```
