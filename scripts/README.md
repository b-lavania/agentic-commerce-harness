# Launch scripts

Every common command has a **`.sh`** (Linux/macOS) and **`.bat`** (Windows) pair. Prefer these over raw `python -m …`.

| Script | Role |
|--------|------|
| `install.sh` / `.bat` | Create `.venv` (if needed) + `pip install -e ".[dev]"` |
| `test.sh` / `.bat` | Full pytest suite |
| `harness.sh` / `.bat` | Cert runner (`run-all` or one scenario) |
| `curriculum.sh` / `.bat` | H1→H2 handoff driver (no Counter) |

Uses `.venv` python if present. Sets `PYTHONPATH=src`.

---

## Linux / macOS

```bash
chmod +x scripts/*.sh

./scripts/install.sh
./scripts/test.sh
./scripts/harness.sh
./scripts/harness.sh --jsonl /tmp/ach-trajectories.jsonl
./scripts/harness.sh --view /tmp/ach-all.html
./scripts/harness.sh run horizons/discovery/scenarios/h1_cloud_seats.json
./scripts/curriculum.sh
./scripts/curriculum.sh --view /tmp/ach-trace.html --out /tmp/handoff.json
./scripts/curriculum.sh --h1 horizons/discovery/scenarios/h1_virtual_bundle.json --out /tmp/handoff.json
```

---

## Windows

```bat
scripts\install.bat
scripts\test.bat
scripts\harness.bat
scripts\harness.bat --jsonl %TEMP%\ach-trajectories.jsonl
scripts\harness.bat --view %TEMP%\ach-all.html
scripts\harness.bat run horizons\discovery\scenarios\h1_cloud_seats.json
scripts\curriculum.bat
scripts\curriculum.bat --view %TEMP%\ach-trace.html --out %TEMP%\handoff.json
scripts\curriculum.bat --h1 horizons\discovery\scenarios\h1_virtual_bundle.json --out %TEMP%\handoff.json
```
