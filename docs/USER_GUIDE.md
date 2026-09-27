# User guide

## Start the dashboard

From the project directory:

```bash
source .venv/bin/activate
streamlit run app.py
```

Open the local URL printed in the terminal. Do not run `run app.py`; `run` is not a shell command.

## Choose a dataset

The sidebar has two data modes:

### Public utility projects

This mode loads the source-linked snapshot in `data/public_projects.json`. The region selector includes:

- **All public regions** — the full Georgia/South Carolina and South Florida demo.
- **Georgia + South Carolina** — the original challenge example.
- **South Florida** — the FPL and Homestead Public Services pilot.

The public records are ready to explore without an API key.

### Uploaded plan documents

This mode reads PDF or text plans from `data/plans/` or from the upload control. Choose **Offline rules** for a local demo. Choose **Claude** only after setting `ANTHROPIC_API_KEY`.

The pipeline extracts project fields, checks their evidence and confidence, and places uncertain records in **Review queue** before they participate in overlap screening.

## Read the dashboard

### Projects

Review the project inventory. Public records include utility, region, schedule, geometry quality, and an official source link. “Approximate” means the public source described an endpoint, county, or preliminary corridor instead of providing route GIS.

### Overlap map

Colored lines and points show project shapes. Red connectors show the closest points between two projects. A thicker connector indicates a shared published build window. Open a coordination card to see the distance, timing state, recommended action, evidence, and source links.

### Timeline

Projects with complete dates appear as bars. Hatched bars belong to at least one geographic candidate. Projects with incomplete dates are intentionally omitted from this view rather than assigned invented dates.

### Review queue

For extracted records, inspect the source excerpt and field confidence. Correct location, dates, type, or voltage, then approve or reject the record. Public-screening records do not need extraction review.

### Metrics

Uploaded records can be compared with the hand-labeled fixtures in `data/labels.csv`. Public mode reports source coverage and does not pretend to measure extraction accuracy.

## Three-minute demo

1. Start in **All public regions** and show the project count and source links.
2. Open **Overlap map** and explain closest-point distance.
3. Open the top coordination card and explain its distance tier.
4. Switch to **South Florida** and show the FPL/Homestead pilot.
5. Switch to **Uploaded plan documents** if you want to demonstrate extraction and human review.

See [DEMO.md](../DEMO.md) for presenter wording.
