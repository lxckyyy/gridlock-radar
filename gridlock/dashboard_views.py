"""Rendering functions for the GridLock Radar dashboard."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import config
from .confidence import low_fields
from .evaluate import evaluate, threshold_sweep
from .extraction.ingest import load_pages
from .models import PROJECT_TYPES, Field, ProjectRecord
from .spatial.geocode import place_options
from .spatial.geometry import latlon_path, line, point
from .storage import store

FIELD_LABELS = {
    "geometry": "Location shape",
    "start_date": "Construction start",
    "end_date": "Construction end",
    "project_type": "Project type",
    "voltage_kv": "Voltage (kV)",
    "location_text": "Location text",
}


def render_project_inventory(records: list[ProjectRecord], is_public: bool) -> None:
    rows = [
        {
            "Utility": record.utility,
            "Region": record.value("region") or "Uploaded plan",
            "Project ID": record.project_id,
            "Project": record.value("project_name"),
            "Voltage (kV)": record.value("voltage_kv"),
            "Start": record.value("start_date") or "Not published",
            "End": record.value("end_date") or "Not published",
            "Location": record.value("location_text"),
            "Geometry quality": record.value("geometry_quality") or "Extracted from plan",
            "Official source": record.value("source_url") or "",
        }
        for record in records
    ]
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Official source": st.column_config.LinkColumn(
                "Official source", display_text="Open source"
            )
        },
    )
    if is_public and records:
        snapshot_date = records[0].value("source_snapshot_date") or "unknown"
        st.caption(
            f"Snapshot retrieved {snapshot_date}. Route estimates are screening geometries, "
            "not filed alignments."
        )


def render_overlap_map(
    records: list[ProjectRecord],
    overlaps,
    utilities: list[str],
    color_by_utility: dict[str, str],
) -> None:
    left, right = st.columns([3, 2])
    with left:
        figure = go.Figure()
        for utility in utilities:
            first_for_utility = True
            for record in records:
                if record.utility != utility or not record.geometry or record.status == "rejected":
                    continue
                latitudes, longitudes = latlon_path(record.geometry)
                approved = record.status in {"auto_approved", "approved", "public_screening"}
                figure.add_trace(
                    go.Scattermap(
                        lat=latitudes,
                        lon=longitudes,
                        mode="lines+markers" if len(latitudes) > 1 else "markers",
                        name=utility,
                        legendgroup=utility,
                        showlegend=first_for_utility,
                        line={"width": 4, "color": color_by_utility[utility]},
                        marker={
                            "size": 12 if len(latitudes) == 1 else 7,
                            "color": color_by_utility[utility],
                        },
                        opacity=1.0 if approved else 0.35,
                        text=(
                            f"{record.project_id}<br>{record.value('project_name')}<br>"
                            f"{record.value('geometry_quality') or record.status}"
                        ),
                        hoverinfo="text",
                    )
                )
                first_for_utility = False

        for opportunity in overlaps:
            figure.add_trace(
                go.Scattermap(
                    lat=[opportunity.point_a[0], opportunity.point_b[0]],
                    lon=[opportunity.point_a[1], opportunity.point_b[1]],
                    mode="lines+markers",
                    line={
                        "width": 3 if opportunity.same_window else 1.5,
                        "color": "rgba(220,38,38,0.8)",
                    },
                    marker={"size": 5, "color": "rgba(220,38,38,0.8)"},
                    showlegend=False,
                    hoverinfo="text",
                    text=(
                        f"{opportunity.tier_label}: {opportunity.distance_km:.1f} km<br>"
                        f"{opportunity.a.project_id} ↔ {opportunity.b.project_id}"
                    ),
                )
            )

        placed = [record for record in records if record.geometry]
        if placed:
            center = {
                "lat": sum(record.lat for record in placed) / len(placed),
                "lon": sum(record.lon for record in placed) / len(placed),
            }
        else:
            center = {"lat": 32.8, "lon": -81.5}
        figure.update_layout(
            map={"style": "carto-positron", "center": center, "zoom": 7},
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            height=560,
            legend={"orientation": "h", "y": 1.02},
        )
        st.plotly_chart(figure, width="stretch")
        st.caption(
            "Faded shapes are waiting for human review. Red connectors show closest points; "
            "thicker connectors also share a published build window."
        )

    with right:
        st.subheader("Coordination opportunities")
        if not overlaps:
            st.info("No cross-utility projects fall within the selected distance.")
        for opportunity in overlaps[:15]:
            if opportunity.same_window:
                timing = f"shared build window ({opportunity.overlap_days} days)"
            elif opportunity.overlap_days is None:
                timing = "schedule not published"
            else:
                timing = "different build windows"
            title = (
                f"{opportunity.tier_label} · {opportunity.distance_km:.1f} km · "
                f"{opportunity.a.project_id} ↔ {opportunity.b.project_id}"
            )
            with st.expander(title):
                st.markdown(f"**Potential coordination:** {opportunity.action}.")
                st.markdown(
                    f"- Closest points: **{opportunity.distance_km:.2f} km** apart\n"
                    f"- Timing: **{timing}**"
                )
                for record in (opportunity.a, opportunity.b):
                    start = record.value("start_date") or "not published"
                    end = record.value("end_date") or "not published"
                    st.markdown(
                        f"**{record.utility}** — {record.value('project_name')} "
                        f"({start} to {end})"
                    )
                    source_url = record.value("source_url")
                    if source_url:
                        st.markdown(
                            f"[Open source: {record.value('source_title')}]({source_url})"
                        )
                        st.caption(record.fields["project_name"].quote)
                        if record.value("schedule_text"):
                            st.caption(f"Published schedule: {record.value('schedule_text')}")
                    else:
                        location = record.fields["location_text"]
                        st.caption(
                            f"Source: {record.document}, page {location.page} — "
                            f"“{location.quote or record.fields['project_name'].quote}”"
                        )
                    quality = record.value("geometry_quality")
                    if quality:
                        st.caption(f"Location quality: {quality}")


def render_timeline(
    records: list[ProjectRecord],
    overlaps,
    color_by_utility: dict[str, str],
) -> None:
    flagged_ids = {
        (record.utility, record.project_id)
        for opportunity in overlaps
        for record in (opportunity.a, opportunity.b)
    }
    rows = [
        {
            "project": f"{record.project_id} {record.value('project_name')}",
            "utility": record.utility,
            "start": record.value("start_date"),
            "end": record.value("end_date"),
            "overlap": "screening candidate"
            if (record.utility, record.project_id) in flagged_ids
            else "no candidate",
            "status": record.status,
        }
        for record in records
        if record.value("start_date")
        and record.value("end_date")
        and record.status != "rejected"
    ]
    if not rows:
        st.info("No projects have a complete published build window.")
        return

    timeline = pd.DataFrame(rows).sort_values("start")
    figure = px.timeline(
        timeline,
        x_start="start",
        x_end="end",
        y="project",
        color="utility",
        pattern_shape="overlap",
        pattern_shape_map={"screening candidate": "/", "no candidate": ""},
        color_discrete_map=color_by_utility,
        hover_data=["status"],
    )
    figure.update_yaxes(autorange="reversed", title=None)
    figure.update_layout(
        height=40 * len(timeline) + 120,
        margin={"l": 0, "r": 0, "t": 30, "b": 0},
    )
    st.plotly_chart(figure, width="stretch")
    st.caption("Hatched bars belong to at least one geographic screening candidate.")


def _highlight_source(page_text: str, quotes: list[str]) -> str:
    output = page_text
    for quote in sorted({quote for quote in quotes if quote}, key=len, reverse=True):
        output = re.sub(
            re.escape(quote),
            lambda match: f"**:orange-background[{match[0]}]**",
            output,
        )
    return output.replace("\n", "  \n")


def render_review_queue(
    queue: list[ProjectRecord], threshold: float, reviewer: str
) -> None:
    if not queue:
        st.success("Review queue is empty. Every extracted project is approved or rejected.")
        return

    places = place_options()
    for record in queue:
        low_confidence_fields = low_fields(record, threshold)
        title = (
            f"{record.utility} · {record.project_id} · "
            f"{record.value('project_name')}"
        )
        with st.expander(title, expanded=record is queue[0]):
            reasons = (
                [f"Low confidence: {', '.join(FIELD_LABELS[field] for field in low_confidence_fields)}"]
                if low_confidence_fields
                else []
            )
            st.warning(" · ".join(reasons + record.issues))
            source_column, form_column = st.columns([1, 1])
            with source_column:
                page_number = record.fields["project_name"].page or 1
                pages = load_pages(config.PLANS_DIR / record.document)
                st.caption(f"{record.document} — page {page_number}")
                if not 1 <= page_number <= len(pages):
                    st.warning("The referenced source page is unavailable.")
                    block = ""
                else:
                    block = pages[page_number - 1]
                project_index = block.find(record.project_id)
                snippet = (
                    block[max(0, project_index - 10):project_index + 600]
                    if project_index >= 0
                    else block[:800]
                )
                st.markdown(
                    _highlight_source(snippet, [field.quote for field in record.fields.values()])
                )

            with form_column:
                for field_name in ("geometry", "start_date", "end_date", "project_type", "voltage_kv"):
                    field = record.fields.get(field_name, Field())
                    icon = "🟢" if field.confidence >= threshold else "🟠"
                    shown_value = (
                        field.value["type"]
                        if field_name == "geometry" and field.value
                        else field.value
                    )
                    note = f" ({field.note})" if field.note else ""
                    st.markdown(
                        f"{icon} **{FIELD_LABELS[field_name]}**: `{shown_value}` — "
                        f"confidence {field.confidence:.2f}{note}"
                    )

                with st.form(f"review-{record.utility}-{record.project_id}"):
                    place_from = st.selectbox(
                        "Set location (or site)", ["(keep)"] + list(places)
                    )
                    place_to = st.selectbox(
                        "Line destination (optional)", ["(none)"] + list(places)
                    )
                    start_date = st.date_input(
                        "Construction start",
                        date.fromisoformat(record.value("start_date"))
                        if record.value("start_date")
                        else None,
                    )
                    end_date = st.date_input(
                        "Construction end",
                        date.fromisoformat(record.value("end_date"))
                        if record.value("end_date")
                        else None,
                    )
                    project_type = st.selectbox(
                        "Project type",
                        PROJECT_TYPES,
                        index=PROJECT_TYPES.index(record.value("project_type") or "other"),
                    )
                    voltage = st.number_input(
                        "Voltage (kV)", value=int(record.value("voltage_kv") or 0), step=1
                    )
                    approve_column, reject_column = st.columns(2)
                    approve = approve_column.form_submit_button("Approve", type="primary")
                    reject = reject_column.form_submit_button("Reject")

                if not (approve or reject):
                    continue
                if approve and start_date and end_date and start_date > end_date:
                    st.error("Construction end must be on or after construction start.")
                    continue
                if approve and place_from != "(keep)" and place_to == place_from:
                    st.error("Choose two different substations for a line.")
                    continue

                changes = {}
                if approve:
                    geometry = record.geometry if place_from == "(keep)" else (
                        point(*places[place_from])
                        if place_to == "(none)"
                        else line([places[place_from], places[place_to]])
                    )
                    edits = {
                        "geometry": geometry,
                        "start_date": start_date.isoformat() if start_date else None,
                        "end_date": end_date.isoformat() if end_date else None,
                        "project_type": project_type,
                        "voltage_kv": voltage or None,
                    }
                    for field_name, new_value in edits.items():
                        field = record.fields.setdefault(field_name, Field())
                        if new_value != field.value:
                            changes[field_name] = (field.value, new_value)
                            field.value = new_value
                            field.note = f"edited by {reviewer}"
                        field.confidence = 1.0
                    record.status = "approved"
                else:
                    record.status = "rejected"
                store.save_record(record)
                store.log_review(record, record.status, reviewer, changes)
                st.rerun()


def render_metrics(
    records: list[ProjectRecord],
    is_public: bool,
    utilities: list[str],
    threshold: float,
) -> None:
    if is_public:
        st.info(
            "Accuracy scores require hand-labeled outcomes. The public snapshot is a "
            "source-linked screening set, not a labeled evaluation set."
        )
        rows = [
            {
                "Utility": utility,
                "Projects": sum(record.utility == utility for record in records),
                "Build window published": sum(
                    record.utility == utility
                    and bool(record.value("start_date") and record.value("end_date"))
                    for record in records
                ),
                "Official source link": sum(
                    record.utility == utility and bool(record.value("source_url"))
                    for record in records
                ),
            }
            for utility in utilities
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(
            "This summarizes source coverage only; it does not estimate extraction accuracy "
            "or route certainty."
        )
        return

    metrics = evaluate(records)
    documents = store.load_documents()
    if metrics.get("labeled"):
        st.caption(
            f"Scored against {metrics['labeled']} hand-labeled projects in data/labels.csv. "
            "Reviewed records include human corrections."
        )
        columns = st.columns(4)
        columns[0].metric("Record accuracy", f"{metrics['record_accuracy']:.0%}")
        columns[1].metric("Auto-approve rate", f"{metrics['auto_approve_rate']:.0%}")
        accuracy = metrics["auto_approved_accuracy"]
        columns[2].metric(
            "Accuracy of auto-approved", f"{accuracy:.0%}" if accuracy is not None else "—"
        )
        total_cost = sum(document["cost_usd"] for document in documents)
        columns[3].metric("Cost per document", f"${total_cost / max(1, len(documents)):.4f}")

        left, right = st.columns(2)
        with left:
            st.markdown("**Field accuracy**")
            field_accuracy = pd.DataFrame(
                {
                    "field": [FIELD_LABELS[field] for field in metrics["field_accuracy"]],
                    "accuracy": list(metrics["field_accuracy"].values()),
                }
            )
            figure = px.bar(
                field_accuracy,
                x="accuracy",
                y="field",
                orientation="h",
                range_x=[0, 1],
                text_auto=".0%",
            )
            figure.update_layout(
                height=260, margin={"l": 0, "r": 0, "t": 10, "b": 0}, yaxis_title=None
            )
            st.plotly_chart(figure, width="stretch")
        with right:
            st.markdown("**Threshold trade-off**")
            sweep = pd.DataFrame(threshold_sweep(records))
            long = sweep.melt(
                id_vars="threshold",
                value_vars=["auto_approve_rate", "auto_approved_accuracy"],
                var_name="measure",
                value_name="share",
            )
            long["measure"] = long["measure"].map(
                {
                    "auto_approve_rate": "Auto-approve rate",
                    "auto_approved_accuracy": "Accuracy of auto-approved",
                }
            )
            figure = px.line(
                long, x="threshold", y="share", color="measure", markers=True, range_y=[0, 1.05]
            )
            figure.add_vline(x=threshold, line_dash="dot")
            figure.update_layout(
                height=260, margin={"l": 0, "r": 0, "t": 10, "b": 0}, legend_title=None
            )
            st.plotly_chart(figure, width="stretch")
    else:
        st.info("No records match the hand-labeled evaluation set yet.")

    st.markdown("**Per document**")
    if documents:
        st.dataframe(pd.DataFrame(documents), hide_index=True, width="stretch")
    st.markdown("**Review log**")
    review_log = store.load_reviews()
    if review_log:
        st.dataframe(pd.DataFrame(review_log), hide_index=True, width="stretch")
    else:
        st.caption("No reviews yet.")
