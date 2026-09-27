# Data sources and provenance

## Public snapshot

The demo snapshot is stored in `data/public_projects.json` and was retrieved on 2026-09-26. Each record includes:

- `source_url` — official page or municipal report.
- `source_title` — human-readable source name.
- `source_quote` — short supporting excerpt.
- `schedule_text` — the published timing language.
- `geometry_quality` — how the map shape was produced.
- `region` — the dashboard filter group.

## Included source groups

| Region | Utility | Source material |
| --- | --- | --- |
| Georgia + South Carolina | Georgia Power | Official transmission project pages and project list |
| Georgia + South Carolina | Dominion Energy South Carolina | Official power-line project pages |
| South Florida | Florida Power & Light | Andytown–Oasis project page |
| South Florida | Homestead Public Services Energy | City Manager reports and HPS project summary |

The exact URLs are retained on every row and exposed as links in the Projects table and opportunity cards.

## Geometry quality

The overlap calculation is only as reliable as the geometry supplied to it:

- **Official route GIS** — suitable for detailed screening.
- **Endpoint chord** — a straight line between named facilities.
- **County or site approximation** — a point used when the source gives only an area description.

The current public snapshot contains endpoint and site approximations. The app deliberately displays this limitation instead of presenting the result as a filed alignment.

## Schedule semantics

Dates are copied or normalized from the source language. If a source gives only a start or only a completion target, the missing side remains empty. The overlap engine represents that schedule as unknown and still allows the geographic candidate to appear.

## Updating the snapshot

1. Add or edit a record in `data/public_projects.json`.
2. Keep the official URL and a short supporting excerpt.
3. Use a `Point` or `LineString` in GeoJSON longitude/latitude order.
4. Describe any approximation in `geometry_quality`.
5. Validate the file and run the tests:

```bash
python -m json.tool data/public_projects.json >/dev/null
pytest -q
```

The dashboard does not scrape utility sites automatically. Review source freshness before presenting the data as current.
