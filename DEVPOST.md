# GridLock Radar

## Inspiration

Electric transmission planning is usually published utility by utility. That makes it difficult to see when two organizations are preparing projects near one another or in the same construction window.

We built GridLock Radar to turn those separate public plans into one explainable coordination screen. The goal is to help utilities spot opportunities to share crews, cranes, access roads, staging areas, permits, or right-of-way before each project plans those resources independently.

## What it does

GridLock Radar compares planned electric utility projects using two signals:

1. **Geographic proximity:** the closest points of two project shapes are within 40 km.
2. **Schedule proximity:** the published construction windows overlap.

Geography is the primary signal. Schedule overlap is used to rank opportunities within the same distance tier.

The app includes:

- An interactive map showing projects from multiple utilities.
- Red connectors showing the closest points between candidate projects.
- Ranked coordination opportunities with recommended actions.
- Distance tiers for crossings, right-of-way, site logistics, and shared crews.
- A timeline view for construction windows.
- Official source links, source excerpts, and geometry-quality notes.
- A South Florida pilot alongside the original Georgia/South Carolina challenge example.
- An upload workflow that extracts projects from plan documents and sends uncertain fields to human review.

## How we built it

We built the application in Python with Streamlit.

- **Streamlit** provides the interactive dashboard and review workflow.
- **Plotly** renders the project map and construction timeline.
- **Shapely** calculates the closest points between project shapes.
- **PyProj** projects coordinates into a local UTM zone before measuring distances.
- **pdfplumber** reads PDF plan documents.
- An offline rules extractor handles structured plans, while an optional **Claude** extractor handles less predictable documents.
- **SQLite** stores extracted projects, document runs, and reviewer audit history.

Public records are stored as validated GeoJSON-style points or lines. Each record keeps its source URL, supporting excerpt, schedule text, and geometry-quality description.

## Challenges we ran into

The biggest challenge was data quality. Public utility pages often describe a project’s endpoints, counties, or preliminary corridor without publishing route GIS. Some pages also provide only a start date or only an expected completion date.

We addressed this by making uncertainty visible. Approximate geometries are labeled, incomplete schedules remain unknown, and every public record links back to its source. The app still shows a geographic candidate when dates are missing, but it does not invent a timeline match.

We also had to make the geographic rule precise. Comparing project centers would miss cases where a long line passes close to another project. GridLock Radar measures the closest points of the actual supplied shapes instead.

## Accomplishments that we're proud of

- Built a working interactive map and ranked coordination list from public records.
- Kept the original Georgia Power/Dominion challenge example and added a South Florida pilot with FPL and Homestead Public Services Energy.
- Made every public result traceable to an official source page or municipal report.
- Added transparent geometry-quality and schedule-availability labels.
- Built a human review queue so low-confidence extracted projects do not silently enter the comparison.
- Added automated tests for closest-point distance, ranking, schedule behavior, public-data validation, and both demo regions.

## What we learned

- The quality of the geometry matters as much as the distance algorithm. A precise calculation over an approximate route is still only a screening result.
- Missing schedule data is different from a known schedule mismatch and should be represented separately.
- A useful infrastructure tool needs evidence and confidence indicators, not just a map.
- A clear demo flow matters: show the project inventory, explain the closest-point connector, then open the ranked opportunity and its source.
- Regional pilots are a practical way to validate the workflow before expanding to a national catalog.

## What's next for GridLock Radar

- Replace endpoint and county approximations with official route GIS or digitized filing maps.
- Add automated source refreshes and source-freshness timestamps.
- Add adapters for utility, ISO/RTO, and state commission planning records.
- Use a spatial index so the app can compare thousands of projects efficiently.
- Detect true route crossings in addition to distance tiers.
- Add rough cost and impact estimates for shared land, access, staging, and equipment.
- Expand the regional pilot toward a national screening catalog.

## Demo

```bash
streamlit run app.py
```

Start with **All public regions**, open **Overlap map**, and select a coordination opportunity. See [DEMO.md](DEMO.md) for the presenter walkthrough and [README.md](README.md) for setup details.
