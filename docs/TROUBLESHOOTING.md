# Troubleshooting

## `zsh: command not found: run`

Use Streamlit explicitly:

```bash
streamlit run app.py
```

Or use the virtual environment directly:

```bash
.venv/bin/streamlit run app.py
```

## The app shows the wrong region

Use the sidebar:

1. Set **Project data** to **Public utility projects**.
2. Set **Public project region** to **All public regions**, **Georgia + South Carolina**, or **South Florida**.

If an older server is still open, press `Ctrl+C` in its terminal and launch again. Always open the URL printed by the newest Streamlit process.

## Florida projects are missing

The current public snapshot contains seven South Florida records. Confirm that the page says **Showing: All public regions · 15 projects** or **Showing: South Florida · 7 projects** beneath the title. If it does not, the browser is connected to an older server or a different checkout.

## Claude extraction is unavailable

The offline rules extractor works without an API key. For Claude, install the requirements and set:

```bash
export ANTHROPIC_API_KEY=your-key
```

Then choose **Claude** in the uploaded-plan mode.

## The map contains no red connector

Red connectors only appear for cross-utility pairs within the selected distance. Set the distance to 40 km, turn off **Require a shared build window**, and choose a region with two utilities.
