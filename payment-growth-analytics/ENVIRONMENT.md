# Environment

Inspected at build time on macOS (Darwin 25.6.0, arm64).

| Tool / Runtime | Available | Version / Notes |
|---|---|---|
| Python | Yes | **3.9.6** (system `/usr/bin/python3`). PRD prefers 3.11+; project is written to be 3.9-compatible (no 3.10+ syntax). |
| `pip` | Yes | 21.2.4 (upgraded inside venv) |
| `uv` | No | Not installed; venv + pip used instead |
| `poetry` | No | Not installed |
| `conda` | No | Not installed |
| `make` | Yes | GNU Make 3.81 |
| Docker | No | `docker-compose.yml` is provided for reference / future use |
| Java / JRE | No | Not required; Tableau Hyper API is pure-Python wheels |
| Node | Yes | v26.3.0 (not used by this project) |
| DuckDB CLI | No | DuckDB used **embedded** via the Python `duckdb` package (v1.4.5) |
| Tableau Desktop | **Yes** | 2026.2 (Apple silicon) — Hyper extract can be opened/validated |
| Tableau Prep Builder | **Yes** | 2026.2 (Apple silicon) |
| Tableau Hyper API | Yes | `tableauhyperapi` 0.0.26479 (installed in venv) |
| Git | Yes | 2.50.1 |

## Notes & adaptations

- **Python 3.9**: the PRD asks for 3.11+. Only 3.9.6 is present and installing a
  second interpreter requires external network/homebrew access that is not
  assumed. All code therefore avoids 3.10+ syntax (no `match`, no `X | Y` union
  types in annotations at runtime, no `ParamSpec` usage). Type hints use
  `typing` constructs so `from __future__ import annotations` is unnecessary.
  This is the single intentional deviation from the PRD's stack guidance.
- **DuckDB** is used embedded (in-process) — no server, no CLI required.
- **Tableau Desktop is available**, so the Hyper extract is structurally valid
  and openable; the generated `.twb` is validated structurally (XML well-formed,
  datasource + sheet definitions present). See `tableau/documentation/tableau_setup.md`.
- No external network access is assumed at runtime; all data is synthetic and
  generated locally.
