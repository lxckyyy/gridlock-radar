# GridLock Radar demo

This is a short, reliable walkthrough for the hackathon presentation. It uses the public-source snapshot that ships with the project, so the demo does not depend on an API key or uploaded files.

## Start the app

```bash
cd gridlock-radar
source .venv/bin/activate
streamlit run app.py
```

The browser opens on **Public utility projects** with **All public regions** selected and the **Show demo guide** enabled. Leave the geographic distance at **40 km** and keep **Require a shared build window** off. The prepared snapshot contains the original eight projects from Georgia Power and Dominion Energy South Carolina plus a South Florida pilot. Use the region selector to focus on either **Georgia + South Carolina** or **South Florida**.

## Three-minute story

1. In **Projects**, point out that each row has a utility, project ID, schedule, geometry-quality note, and a link back to the official utility page.
2. Open **Overlap map**. Explain that the red connector joins the closest points of two project shapes; it is not a center-to-center distance.
3. Open the top opportunity card. The prepared result is Dominion’s `DESC-JASPER-OKATIE-SHERWOOD-230KV` and Georgia Power’s `GP-EFFINGHAM-500KV-AREA`, about 36 km apart. The card calls this an **Under 40 km** candidate, which means shared crews, cranes, or contractors are worth investigating.
4. Click the source links in the opportunity card. This demonstrates traceability: the app is a screening layer over public records, not a replacement for the official project page.
5. Open **Timeline** to show the secondary signal. If a project has no published completion date, the app says so instead of inventing a schedule match.

To show the added pilot, choose **South Florida** in the **Public project region** selector. The prepared comparison is FPL’s Andytown–Oasis lines against Homestead Public Services Energy projects such as the Donnie Avocado and Redland substations. The app ranks the closest-point candidates while keeping the approximate geometry warning visible.

## What to say if asked

- “The geographic rule is the primary signal: closest points within 40 km. Timing only changes the ranking when dates are available.”
- “The public pages do not consistently publish route GIS, so the starter shapes are labeled approximate. A production version would replace them with official GeoJSON or digitized filings.”
- “The same interface can switch to uploaded plan documents, run offline extraction, and send uncertain fields to the review queue.”

## Backup path

Switch **Project data** to **Uploaded plan documents** if you want to show the extraction workflow. Use the offline rules extractor, click **Re-run plan extraction**, then open **Review queue** to show human approval before a project can participate in overlap screening.
