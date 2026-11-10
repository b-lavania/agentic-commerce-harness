# Harness

Cert runner lives in `src/ach/harness/`.

```bash
pip install -e ".[dev]"
python -m ach.harness.cli run-all
python -m ach.harness.cli run-all --jsonl /tmp/ach-trajectories.jsonl
python -m ach.harness.cli run horizons/discovery/scenarios/h1_branch_ngfw.json
```
