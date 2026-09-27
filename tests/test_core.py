from datetime import date

from gridlock import config
from gridlock.confidence import score
from gridlock.extraction.dates import parse_window
from gridlock.evaluate import evaluate
from gridlock.extraction.extract_rules import extract
from gridlock.models import Field, ProjectRecord
from gridlock.spatial.geometry import distance_km, line, point
from gridlock.spatial.geocode import geocode
from gridlock.spatial.overlap import find_overlaps, geo_tier, window_overlap_days
from gridlock.pipeline import run


def test_parse_window_precision_sets_confidence():
    assert parse_window("March 2027 – October 2027") == (date(2027, 3, 1), date(2027, 10, 31), 0.95)
    assert parse_window("Q2 2027 - Q3 2027")[:2] == (date(2027, 4, 1), date(2027, 9, 30))
    assert parse_window("Summer 2027")[2] < config.CONFIDENCE_THRESHOLD
    assert parse_window("2028") == (date(2028, 1, 1), date(2028, 12, 31), 0.60)
    assert parse_window("TBD") is None


def test_distance_uses_closest_points_not_centers():
    # A 60 km east-west line whose midpoint is far from the substation, but whose end is 5 km away.
    long_line = line([(33.50, -82.30), (33.50, -81.655)])
    substation = point(33.545, -81.655)  # ~5 km north of the line's east end
    assert 4.5 < distance_km(long_line, substation) < 5.5


def test_one_degree_of_latitude_is_about_111_km():
    assert abs(distance_km(point(33, -81), point(34, -81)) - 110.9) < 0.5


def test_geo_tiers():
    labels = {d: config.GEO_TIERS[geo_tier(d)][1] if geo_tier(d) is not None else None for d in (0, 1.0, 5, 39, 41)}
    assert labels == {0: "Touching / crossing", 1.0: "Under 1.6 km", 5: "Under 8 km", 39: "Under 40 km", 41: None}


def test_window_overlap_days():
    assert window_overlap_days(date(2027, 1, 1), date(2027, 3, 31), date(2027, 3, 1), date(2027, 6, 30)) == 31
    assert window_overlap_days(date(2027, 1, 1), date(2027, 3, 31), date(2027, 5, 1), date(2027, 6, 30)) == 0


def test_substation_names_inside_other_names_are_not_double_counted():
    geom, _, _ = geocode("North Augusta substation to Aiken substation, Aiken County")
    assert geom["type"] == "LineString" and len(geom["coordinates"]) == 2


def _record(pid, utility, geom, start, end, status="auto_approved"):
    fields = {
        "geometry": Field(geom, 1.0),
        "start_date": Field(start, 1.0),
        "end_date": Field(end, 1.0),
        "project_type": Field("transformer", 1.0),
        "voltage_kv": Field(138, 1.0),
    }
    return ProjectRecord(pid, utility, "doc", fields, status=status)


def test_overlaps_ranked_by_tier_then_same_window():
    tie = line([(33.4735, -82.0105), (33.5018, -81.9651)])
    a_touch = _record("A1", "Alpha", point(33.5018, -81.9651), "2028-01-01", "2028-06-30")  # touches, other window
    a_near = _record("A2", "Alpha", point(33.60, -81.9651), "2027-04-01", "2027-09-30")  # ~11 km, same window
    a_far = _record("A3", "Alpha", point(34.50, -81.9651), "2027-04-01", "2027-09-30")  # >100 km
    b = _record("B1", "Beta", tie, "2027-06-01", "2027-12-31")
    pending = _record("B2", "Beta", tie, "2027-06-01", "2027-12-31", status="needs_review")
    found = find_overlaps([a_touch, a_near, a_far, b, pending])
    assert [(o.a.project_id, o.b.project_id) for o in found] == [("A1", "B1"), ("A2", "B1")]
    assert found[0].tier_label == "Touching / crossing" and not found[0].same_window
    assert find_overlaps([a_touch, a_near, b], same_window_only=True)[0].a.project_id == "A2"


def test_vague_location_goes_to_review():
    pages = ["Utility: Test\nProject TST-2028-001: New 69 kV substation\nLocation: near Nowhere\n"
             "Construction: March 2028 - May 2028\n"]
    (record,) = extract(pages, "Test", "doc.txt")
    score(record)
    assert record.status == "needs_review"
    assert record.geometry is None


def test_nonstandard_voltage_is_flagged():
    pages = ["Project TST-2028-002: Hardeeville 135 kV Line Rebuild\nLocation: Hardeeville substation\n"
             "Construction: April 2028 – September 2028\n"]
    (record,) = extract(pages, "Test", "doc.txt")
    score(record)
    assert record.status == "needs_review"
    assert any("135 kV" in issue for issue in record.issues)


def test_sample_data_auto_approved_records_are_all_correct(tmp_path):
    records = run("rules", db=tmp_path / "t.db")
    m = evaluate(records)
    assert m["labeled"] == 15
    assert m["auto_approved_accuracy"] == 1.0
    assert 0.5 <= m["auto_approve_rate"] < 1.0


def test_claude_output_is_checked_against_the_page():
    from gridlock.extraction.extract_llm import to_records

    pages = ["Project X-1: Evans 115 kV Substation Expansion\nSite: Evans substation\nTiming: 2028\n"]
    project = {
        "project_id": "X-1", "project_name": "Evans 115 kV Substation Expansion", "project_type": "substation",
        "voltage_kv": 115, "location_text": "Evans substation", "schedule_text": "2028",
        "construction_start": "2028-01-01", "construction_end": "2028-12-31", "status": None, "page": 1,
        "source_quote": "Project X-1: Evans 115 kV Substation Expansion",
        "confidence": {k: 0.95 for k in ("project_type", "voltage_kv", "location_text",
                                          "construction_start", "construction_end")},
    }
    (good,) = to_records({"utility": "Test", "projects": [project]}, pages, "doc.txt")
    assert good.confidence("start_date") == 0.60  # "2028" alone caps Claude's 0.95
    assert good.confidence("location_text") == 0.95

    invented = dict(project, source_quote="Project X-1: something not in the document")
    (bad,) = to_records({"utility": "Test", "projects": [invented]}, pages, "doc.txt")
    assert bad.issues and bad.confidence("project_type") <= 0.30


def test_geographic_candidate_is_kept_when_public_schedule_is_missing():
    a = _record("A-MISSING", "Alpha", point(33.50, -82.00), None, None, status="public_screening")
    b = _record("B-DATED", "Beta", point(33.51, -82.00), "2027-01-01", "2027-12-31")
    (candidate,) = find_overlaps([a, b])
    assert candidate.overlap_days is None
    assert not candidate.same_window
    assert find_overlaps([a, b], same_window_only=True) == []


def test_public_project_snapshot_has_two_utilities_and_source_links():
    from gridlock.public_data import load_public_projects

    records = load_public_projects()
    assert len({r.utility for r in records}) >= 2
    assert all(r.value("source_url").startswith("https://") for r in records)
    assert all(r.status == "public_screening" for r in records)


def test_public_snapshot_keeps_both_demo_regions():
    from gridlock.public_data import load_public_projects

    records = load_public_projects()
    regions = {record.value("region") for record in records}
    assert {"Georgia + South Carolina", "South Florida"} <= regions
    florida = [record for record in records if record.value("region") == "South Florida"]
    assert {record.utility for record in florida} == {
        "Florida Power & Light",
        "Homestead Public Services Energy",
    }
    assert find_overlaps(florida)
