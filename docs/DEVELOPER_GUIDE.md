# Developer guide

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Useful commands:

```bash
make demo   # run Streamlit
make test   # run pytest
make check  # tests plus Python AST parsing
```

## Where to make changes

- Page controls and data loading: `gridlock/dashboard.py`.
- Streamlit rendering functions: `gridlock/dashboard_views.py`.
- Public record validation: `gridlock/public_data.py`.
- Distance and closest-point logic: `gridlock/spatial/geometry.py`.
- Candidate ranking: `gridlock/spatial/overlap.py`.
- Document extraction: `gridlock/extraction/`.
- Confidence and review routing: `gridlock/confidence.py`.
- SQLite persistence: `gridlock/storage/store.py`.

Keep the controller in `dashboard.py` small. Put view-specific tables, charts, and cards in `dashboard_views.py`.

## Add a public project

Use the existing schema in `data/public_projects.json`:

```json
{
  "project_id": "UTILITY-PROJECT-ID",
  "utility": "Utility name",
  "region": "South Florida",
  "project_name": "Readable project name",
  "project_type": "new_line",
  "voltage_kv": 230,
  "location_text": "Published location description",
  "start_date": "2028-01-01",
  "end_date": "2030-12-31",
  "schedule_text": "Published schedule wording",
  "geometry": {"type": "Point", "coordinates": [-80.4, 25.6]},
  "geometry_quality": "Approximate site point; source does not publish route coordinates.",
  "source_title": "Official source",
  "source_url": "https://example.com/project",
  "source_quote": "Short supporting excerpt."
}
```

Coordinates are `[longitude, latitude]`. Dates use ISO `YYYY-MM-DD`. The loader requires an HTTP source URL, valid coordinates, a supported project type, and at least two utilities in the complete snapshot.

## Change overlap behavior

The overlap engine follows this order:

1. Compare only comparable records with geometry.
2. Measure closest-point distance in kilometers.
3. Drop pairs outside the selected maximum distance.
4. Assign the closest geographic tier.
5. Calculate schedule overlap when all four dates are known.
6. Rank by geographic tier, shared window, unknown schedule, known non-overlap, and exact distance.

Update or add tests in `tests/test_core.py` when changing this behavior.

## Storage and generated files

Uploaded-document records use SQLite at `gridlock.db` by default. Set `GRIDLOCK_DB` to use another path. The database, virtual environment, caches, and secrets are ignored by `.gitignore` and should not be uploaded to Devpost.

## Pull-request quality check

Before sharing a change:

```bash
git diff --check
make check
python -m pyflakes app.py gridlock tests
```
