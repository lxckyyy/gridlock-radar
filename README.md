# GridLock Radar

GridLock Radar is an interactive screening tool for finding coordination opportunities between planned electric utility projects. It compares the closest points of project shapes, ranks pairs within 40 km, and uses construction timing as a secondary signal.

The demo includes two public-data regions:

- **Georgia + South Carolina:** Georgia Power and Dominion Energy South Carolina, matching the challenge example.
- **South Florida:** Florida Power & Light and Homestead Public Services Energy.

The app also accepts plan documents, extracts project fields, and routes uncertain records through a human review queue.

## What the demo shows

- Interactive map with utility projects and red closest-point connectors.
- Ranked coordination opportunities by distance tier.
- Timeline view showing shared, different, or unpublished build windows.
- Source links and geometry-quality notes for every public record.
- Upload workflow with offline extraction, optional Claude extraction, confidence checks, and reviewer approval.

## Run locally

```bash
cd gridlock-radar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL printed by Streamlit. The default view is **All public regions**. Use the sidebar to focus on the original Georgia/South Carolina example or the South Florida pilot.

Run the checks with:

```bash
pytest -q
```

The optional Claude extractor needs both the `anthropic` package and an API key:

```bash
export ANTHROPIC_API_KEY=your-key
python -m gridlock.pipeline --extractor claude
```

## Overlap model

Geographic proximity is the primary signal. The app measures the closest points between two project shapes, so a long line can match a nearby substation even when their centers are far apart.

| Distance tier | Coordination opportunity |
| --- | --- |
| ≤ 0.1 km | Coordinate crossings, outages, and structures |
| ≤ 1.6 km | Share right-of-way, access roads, and permits |
| ≤ 8 km | Share laydown yards and deliveries |
| ≤ 40 km | Share crews, cranes, and contractors |

Build-window overlap is used to rank pairs within the same geographic tier. Missing dates remain explicitly unknown; the app does not infer a schedule match.

## Architecture

```text
public snapshot ───────────────────────────────┐
                                                ├─► overlap engine ─► map, ranked list, timeline
plan PDF/TXT ─► extraction ─► confidence checks ─┘
                                      │
                                      └─► review queue ─► approved records
```

| Area | Responsibility |
| --- | --- |
| `gridlock/dashboard.py` | Streamlit page, controls, data-source selection |
| `gridlock/dashboard_views.py` | Map, project table, timeline, review, and metrics views |
| `gridlock/public_data.py` | Validated source-linked public snapshot loader |
| `gridlock/spatial/geometry.py` | Closest-point distance in a local projected coordinate system |
| `gridlock/spatial/overlap.py` | Distance tiers, schedule overlap, and ranking |
| `gridlock/extraction/` | PDF/text ingestion and rules or Claude extraction |
| `gridlock/confidence.py` | Field checks and human-review routing |
| `gridlock/storage/` | SQLite records and review audit log |
| `data/public_projects.json` | Public demo records and source links |

## Data notes

`data/public_projects.json` is a curated snapshot retrieved on 2026-09-26. The records preserve an official source URL, a short supporting excerpt, schedule text, and a geometry-quality note.

Many public utility pages describe endpoints, counties, or preliminary corridors without publishing route GeoJSON. Those records are labeled as approximate screening geometries. They are useful for a hackathon demonstration, but should be replaced with filed route data before operational use.

The fallback documents in `data/plans/` are synthetic examples for demonstrating extraction and review. They are clearly labeled and are not presented as utility filings.

## Repository layout

```text
app.py                     Streamlit launcher
gridlock/                  Application package
data/public_projects.json  Public demo snapshot
data/plans/                Synthetic extraction fixtures
tests/                     Automated checks
DEMO.md                    Presenter walkthrough
DEVPOST.md                 Submission-ready project description
docs/                       User, data, architecture, and developer guides
```

## Limitations and next steps

- Replace approximate shapes with official route GIS where available.
- Add regional source adapters and freshness checks for automated updates.
- Use a spatial index when the project catalog grows beyond a few thousand records.
- Add cost models for shared land, access, staging, and equipment.
- Add route-crossing detection in addition to the distance tier.

## License

MIT. See [LICENSE](LICENSE).
