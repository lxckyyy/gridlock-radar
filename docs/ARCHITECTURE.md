# Architecture notes

## Data flow

1. Public records are loaded from `data/public_projects.json` and validated before they reach the dashboard.
2. Uploaded PDF or text plans pass through an extractor.
3. Extracted fields receive confidence scores and source evidence.
4. Geometry, voltage, date, and territory checks route uncertain records to review.
5. Approved or public-screening records enter the overlap engine.
6. The dashboard renders the map, ranked opportunities, timeline, and source evidence.

## Key design decisions

- Store geometries as GeoJSON-style longitude/latitude dictionaries so public records and extracted records share one model.
- Project both shapes into a local UTM zone before measuring distance in kilometers.
- Keep geographic distance primary and schedule overlap secondary.
- Represent missing dates as unknown instead of treating them as non-overlapping.
- Keep approximate public geometry visible through an explicit quality note.
- Keep the public snapshot separate from the uploaded-document SQLite workflow.
