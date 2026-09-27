"""Run the whole pipeline: documents -> extraction -> confidence routing -> database -> overlaps.

    python -m gridlock.pipeline                 # rule extractor, offline
    python -m gridlock.pipeline --extractor claude
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import config
from .confidence import score
from .evaluate import evaluate
from .extraction import extract_llm, extract_rules
from .extraction.ingest import list_documents, load_pages, utility_name
from .models import ProjectRecord
from .spatial.overlap import find_overlaps
from .storage import store


def process_document(path: Path, extractor: str = "rules", threshold: float = config.CONFIDENCE_THRESHOLD,
                     db=None) -> list[ProjectRecord]:
    pages = load_pages(path)
    if extractor == "claude":
        records, stats = extract_llm.extract(pages, path.name)
    else:
        started = time.perf_counter()
        records = extract_rules.extract(pages, utility_name(pages, path.stem), path.name)
        stats = {"latency_ms": (time.perf_counter() - started) * 1000}

    for record in records:
        score(record, threshold)
        store.save_record(record, db)
    utility = records[0].utility if records else utility_name(pages, path.stem)
    store.save_document(path.name, utility, extractor, len(records), stats, db)
    return records


def run(extractor: str = "rules", threshold: float = config.CONFIDENCE_THRESHOLD, folder: Path = config.PLANS_DIR,
        db=None) -> list[ProjectRecord]:
    if extractor == "claude" and not extract_llm.available():
        raise SystemExit("Claude extractor needs the anthropic package and ANTHROPIC_API_KEY set.")
    store.reset(db)
    records = []
    for path in list_documents(folder):
        records += process_document(path, extractor, threshold, db)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extractor", choices=("rules", "claude"), default="rules")
    parser.add_argument("--threshold", type=float, default=config.CONFIDENCE_THRESHOLD)
    args = parser.parse_args()

    records = run(args.extractor, args.threshold)
    auto = [r for r in records if r.status == "auto_approved"]
    print(f"Extracted {len(records)} projects; {len(auto)} auto-approved, {len(records) - len(auto)} sent to review.\n")

    for r in records:
        if r.status == "needs_review":
            low = [f for f in config.CRITICAL_FIELDS if r.confidence(f) < args.threshold]
            print(f"  REVIEW {r.project_id:<14} low: {', '.join(low) or '-'}  {'; '.join(r.issues)}")

    print(f"\nOverlaps between auto-approved projects (closest points within {config.MAX_OVERLAP_KM:.0f} km):")
    for o in find_overlaps(records):
        window = f"same window ({o.overlap_days} days)" if o.same_window else "different windows"
        print(f"  {o.tier_label:<20} {o.distance_km:6.2f} km  {window:<24} {o.a.project_id} <-> {o.b.project_id}"
              f"  -> {o.action}")

    m = evaluate(records)
    if m.get("labeled"):
        auto_acc = m["auto_approved_accuracy"]
        auto_acc_text = f"{auto_acc:.0%}" if auto_acc is not None else "n/a"
        print(f"\nAgainst {m['labeled']} labeled projects: record accuracy {m['record_accuracy']:.0%}, "
              f"auto-approve rate {m['auto_approve_rate']:.0%}, accuracy of auto-approved {auto_acc_text}")
    for doc in store.load_documents():
        print(f"  {doc['document']}: {doc['projects']} projects, ${doc['cost_usd']:.4f}, {doc['latency_ms']:.0f} ms")


if __name__ == "__main__":
    main()
