# Zdrowa Trasa

Healthier walking and cycling routes for Kraków (competition "Open Data App"). Work in progress: Phase 0.
Read `CLAUDE.md` and `docs/PLAN.md` first.

```sh
make setup      # uv venv (Python 3.12) + dependencies
make test       # pytest (no live API calls)
make lint       # ruff + black --check
make noise      # build data/processed/noise_{LDWN,LN}_10m.tif from data/raw/noise/
make air-once   # one air-quality archiver run
./ops/install_launchd.sh   # hourly archiver on macOS
```

Hourly archiver elsewhere (Linux cron): `7 * * * * cd /path/to/health-path && .venv/bin/python -m etl.air >> logs/air.log 2>&1`

Air data: © Główny Inspektorat Ochrony Środowiska, Portal Jakość Powietrza (API). Data are not continuously verified.
Inspiration: DigitalGeographyLab/green-paths-2 (MIT).
