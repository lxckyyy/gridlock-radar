"""Streamlit application entry point for GridLock Radar."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from . import config
from .extraction import extract_llm
from .pipeline import process_document, run
from .public_data import load_public_projects
from .spatial.overlap import find_overlaps
from .storage import store
from .dashboard_views import (
    render_metrics,
    render_overlap_map,
    render_project_inventory,
    render_review_queue,
    render_timeline,
)

UTILITY_COLORS = ("#087E8B", "#D97706", "#4263EB", "#9C36B5", "#2F9E44")


def _process_upload(upload, extractor: str, threshold: float) -> int:
    """Save and process one upload without overwriting existing source material."""
    filename = Path(upload.name.replace("\\", "/")).name
    if not filename or Path(filename).suffix.lower() not in {".pdf", ".txt"}:
        raise ValueError("Choose a PDF or text plan with a valid filename.")

    destination = config.PLANS_DIR / filename
    if destination.exists():
        raise FileExistsError(f"{filename} already exists in the plans folder. Rename the upload to avoid overwriting it.")

    destination.write_bytes(upload.getvalue())
    selected_extractor = extractor if extractor != "claude" or extract_llm.available() else "rules"
    return len(process_document(destination, selected_extractor, threshold))


def main() -> None:
    st.set_page_config(page_title="GridLock Radar", page_icon="⚡", layout="wide")
    st.session_state.setdefault("public_region_v2", "All public regions")
    st.session_state.setdefault("project_data_source", "Public utility projects")
    if st.session_state.pop("_use_uploaded_data", False):
        st.session_state["project_data_source"] = "Uploaded plan documents"

    with st.sidebar:
        st.title("GridLock Radar")
        st.caption("Compare planned transmission work across neighboring utilities.")
        demo_mode = st.toggle(
            "Show demo guide",
            value=True,
            help="Keeps the short presenter path visible while you walk through the app.",
        )
        data_source = st.radio(
            "Project data",
            ("Public utility projects", "Uploaded plan documents"),
            key="project_data_source",
            help="Public records are source-linked screening data. Uploaded plans use extraction and human review.",
        )
        region = "All public regions"
        if data_source == "Public utility projects":
            region = st.selectbox(
                "Public project region",
                ("All public regions", "Georgia + South Carolina", "South Florida"),
                key="public_region_v2",
                help="Keep the original challenge example and switch to the South Florida pilot without changing the code or data.",
            )
        max_km = st.slider(
            "Geographic screening distance (km)", 1, 80, int(config.MAX_OVERLAP_KM)
        )
        same_window_only = st.checkbox(
            "Require a shared build window",
            help="Pairs with unpublished or non-overlapping schedules are excluded.",
        )

        threshold = config.CONFIDENCE_THRESHOLD
        reviewer = "reviewer"
        if data_source == "Uploaded plan documents":
            extractor_available = extract_llm.available()
            extractor = st.radio(
                "Extraction method",
                ("rules", "claude"),
                format_func={"rules": "Offline rules", "claude": f"Claude ({config.CLAUDE_MODEL})"}.get,
                help=None if extractor_available else "Set ANTHROPIC_API_KEY to enable Claude.",
            )
            threshold = st.slider(
                "Auto-approve confidence", 0.5, 0.95, config.CONFIDENCE_THRESHOLD, 0.05
            )
            reviewer = st.text_input("Reviewer", "reviewer")

            if st.button("Re-run plan extraction", type="primary"):
                if extractor == "claude" and not extractor_available:
                    st.error("Claude requires the anthropic package and ANTHROPIC_API_KEY.")
                else:
                    with st.spinner("Extracting projects from plan documents…"):
                        run(extractor, threshold)
                    st.session_state["_use_uploaded_data"] = True
                    st.rerun()

            upload = st.file_uploader("Add a plan document", type=("pdf", "txt"))
            if upload is not None and st.button("Process document"):
                try:
                    with st.spinner("Reading and extracting projects…"):
                        count = _process_upload(upload, extractor, threshold)
                except (OSError, ValueError, FileExistsError) as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Extracted {count} projects from {Path(upload.name).name}.")
                    st.session_state["_use_uploaded_data"] = True
                    st.rerun()

    if data_source == "Public utility projects":
        try:
            records = load_public_projects()
        except (OSError, ValueError) as exc:
            st.error(f"Could not load the public project snapshot: {exc}")
            st.stop()
        if region != "All public regions":
            records = [record for record in records if record.value("region") == region]
    else:
        records = store.load_records()
        if not records:
            st.info("No extracted records yet. Loading the clearly labeled synthetic sample plans.")
            records = run("rules", threshold)

    st.title("GridLock Radar")
    view_label = f"{region} · {len(records)} projects" if data_source == "Public utility projects" else "Uploaded plan documents"
    st.caption(f"Find nearby transmission projects that may be easier to coordinate together. Showing: {view_label}.")

    utilities = sorted({record.utility for record in records})
    color_by_utility = {
        utility: UTILITY_COLORS[index % len(UTILITY_COLORS)]
        for index, utility in enumerate(utilities)
    }
    overlaps = find_overlaps(records, max_km, same_window_only)
    review_queue = [record for record in records if record.status == "needs_review"]

    if demo_mode:
        with st.expander("Demo guide · 3 minutes", expanded=True):
            st.markdown(
                "**1. Projects** — show that the app combines two utility portfolios and keeps an official source link on every row.  "
                "**2. Overlap map** — open the map and click the red connector to explain closest-point distance.  "
                "**3. Coordination opportunity** — open the top card and explain the suggested shared logistics."
            )
            if overlaps:
                top = overlaps[0]
                schedule = "published build windows overlap" if top.same_window else "one project has no published completion date"
                st.success(
                    f"Top candidate: **{top.a.project_id} ↔ {top.b.project_id}** · "
                    f"{top.distance_km:.1f} km apart · {schedule}."
                )
            else:
                st.info("No candidate is inside the current filter. Set the distance to 40 km to use the prepared demo result.")

    metric_columns = st.columns(4)
    metric_columns[0].metric("Projects", len(records))
    metric_columns[1].metric("Utilities", len(utilities))
    metric_columns[2].metric(
        "With build window",
        sum(bool(record.value("start_date") and record.value("end_date")) for record in records),
    )
    metric_columns[3].metric(
        "Screening candidates" if data_source == "Public utility projects" else "Overlaps flagged",
        len(overlaps),
    )

    if data_source == "Public utility projects":
        source_label = (
            "Florida Power & Light and Homestead Public Services Energy"
            if region == "South Florida"
            else "Georgia Power and Dominion Energy South Carolina"
            if region == "Georgia + South Carolina"
            else "Georgia Power, Dominion Energy South Carolina, Florida Power & Light, and Homestead Public Services Energy"
        )
        st.info(
            f"Public-source snapshot from {source_label}. Some shapes are endpoint or county/site approximations, not official route GIS. "
            "Use distances for screening and check each linked source before acting on a candidate."
        )

    project_tab, map_tab, timeline_tab, review_tab, metrics_tab = st.tabs(
        ("Projects", "Overlap map", "Timeline", f"Review queue ({len(review_queue)})", "Metrics")
    )
    with project_tab:
        render_project_inventory(records, data_source == "Public utility projects")
    with map_tab:
        render_overlap_map(records, overlaps, utilities, color_by_utility)
    with timeline_tab:
        render_timeline(records, overlaps, color_by_utility)
    with review_tab:
        render_review_queue(review_queue, threshold, reviewer)
    with metrics_tab:
        render_metrics(
            records,
            data_source == "Public utility projects",
            utilities,
            threshold,
        )
