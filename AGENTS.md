# AGENTS.md

Guidance for anyone, human or coding agent, changing this repository. [README.md](README.md) is the user
documentation. `CLAUDE.md` only points here.

## Layout

| Path | Content |
|------|---------|
| `custom_components/heating_circuit_advisor/analysis.py` | The analysis in plain Python, without Home Assistant: averages, comfort phase, verdict, setpoint hint, the memory |
| `custom_components/heating_circuit_advisor/coordinator.py` | Reads the circuit, the rooms (areas) and the loops (label) every 4 minutes; stores the memory |
| `custom_components/heating_circuit_advisor/config_flow.py` | Adding a circuit; its options (rooms, settings) |
| `custom_components/heating_circuit_advisor/sensor.py`, `binary_sensor.py` | The entities |
| `custom_components/heating_circuit_advisor/strings.json`, `translations/` | The texts, in English and German |
| `tests/` | pytest-homeassistant-custom-component; `test_analysis.py` needs no Home Assistant |

## Commands

```bash
pip install -r requirements_test.txt   # the pinned Home Assistant of the tests (Python 3.14)
pytest --cov=custom_components/heating_circuit_advisor --cov-fail-under=100
ruff check custom_components tests
```

## Rules

1. **Read only.** The integration never writes to a heater, thermostat or valve. A feature that writes (e.g.
   aligning the heater's schedule with the thermostats') is its own change, off by default, with a mode that
   only shows what it would do.
2. **The analysis stays plain Python** in `analysis.py`, testable without Home Assistant; the coordinator only
   reads states and registries.
3. **Every behavior change comes with a test**; coverage stays at 100 %.
4. **No personal data** in code, tests, issues or commits: no real names, addresses, room names of a real
   house. Test data uses made-up rooms.
5. **English** for code, comments, commits and pull requests; texts in `strings.json` and every translation.
6. **Comments explain why**; a value taken from an observation says so (date and measure).
