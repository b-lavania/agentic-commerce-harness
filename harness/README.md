# Harness

Cert runner lives in `src/ach/harness/`.

```bash
pip install -e ".[dev]"
python -m ach.harness.cli run-all
python -m ach.harness.cli run-all --jsonl /tmp/ach-trajectories.jsonl
python -m ach.harness.cli run-all --view /tmp/ach-all.html
python -m ach.harness.cli run horizons/discovery/scenarios/h1_office_laptop.json
python -m ach.driver.curriculum --view /tmp/ach-trace.html
```
