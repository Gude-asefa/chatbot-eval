"""Excel -> `questions` table pipeline (pure Python: openpyxl only, no pandas).

CLI (from the project root):
    python -m pipeline.ingest                      # uses first .xlsx found in data/
    python -m pipeline.ingest data/MyFile.xlsx
    python -m pipeline.ingest --keep-missing       # do not deactivate questions absent from the file

The admin page "Question bank" tab runs the same functions on an uploaded file.
Re-running is safe: rows are matched on Question ID (insert new, update changed).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from openpyxl import load_workbook

from db import LANGUAGES, SECTIONS, make_engine, metadata, questions

COLUMN_MAP = {
    "Department": "department",
    "Section": "section",
    "Category": "category",
    "Question ID": "question_id",
    "Question Type": "question_type",
    "Language": "language",
    "Question / Test Instructions": "question_text",
    "Expected Answer": "expected_answer",
    "Is Active": "is_active",
}
REQUIRED = ["Department", "Section", "Category", "Question ID", "Language", "Question / Test Instructions"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_FALSE = {"no", "n", "false", "0", "inactive"}


def load_excel(source) -> list[dict]:
    """Read the first sheet into a list of {header: text}. `source` = path or file-like object."""
    wb = load_workbook(source, read_only=True, data_only=True)
    rows = wb.active.iter_rows(values_only=True)
    try:
        headers = [str(h).strip() if h is not None else "" for h in next(rows)]
    except StopIteration:
        return []
    out = []
    for row in rows:
        if row is None or all(v is None or str(v).strip() == "" for v in row):
            continue
        out.append({h: ("" if v is None else str(v).strip()) for h, v in zip(headers, row) if h})
    wb.close()
    return out


def clean(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Validate and normalize. Returns (records, problems). Any problem blocks the sync."""
    problems: list[str] = []
    if not rows:
        return [], ["The file has no data rows."]
    missing = [c for c in REQUIRED if c not in rows[0]]
    if missing:
        return [], [f"Missing required column(s): {', '.join(missing)}"]

    records = []
    for r in rows:
        rec = {dst: r.get(src, "").strip() for src, dst in COLUMN_MAP.items()}
        rec["section"] = rec["section"].title()
        rec["language"] = rec["language"].title()
        rec["is_active"] = rec["is_active"].lower() not in _FALSE
        if rec["question_id"]:
            records.append(rec)

    for col in ["department", "section", "category", "language", "question_text"]:
        n = sum(1 for r in records if not r[col])
        if n:
            problems.append(f"{n} row(s) have an empty '{col}'.")
    bad_sec = sorted({r["section"] for r in records} - set(SECTIONS) - {""})
    if bad_sec:
        problems.append(f"Unknown Section value(s): {bad_sec}. Allowed: {SECTIONS}.")
    bad_lang = sorted({r["language"] for r in records} - set(LANGUAGES) - {""})
    if bad_lang:
        problems.append(f"Unknown Language value(s): {bad_lang}. Allowed: {LANGUAGES}.")
    seen, dups = set(), []
    for r in records:
        if r["question_id"] in seen and r["question_id"] not in dups:
            dups.append(r["question_id"])
        seen.add(r["question_id"])
    if dups:
        problems.append(f"Duplicate Question ID(s): {dups[:10]}{' ...' if len(dups) > 10 else ''}")
    return records, problems


def sync(records: list[dict], engine: sa.Engine, deactivate_missing: bool = True) -> dict:
    """Upsert cleaned rows into `questions`. Returns counts."""
    now = datetime.now(timezone.utc)
    records = [{**r, "updated_at": now} for r in records]
    value_cols = [k for k in COLUMN_MAP.values() if k != "question_id"]

    with engine.begin() as conn:
        existing = {r.question_id: r for r in conn.execute(sa.select(questions))}
        to_insert, updated = [], 0
        for r in records:
            old = existing.get(r["question_id"])
            if old is None:
                to_insert.append(r)
            elif any(getattr(old, k) != r[k] for k in value_cols):
                conn.execute(
                    sa.update(questions)
                    .where(questions.c.question_id == r["question_id"])
                    .values({k: r[k] for k in value_cols + ["updated_at"]})
                )
                updated += 1
        if to_insert:
            conn.execute(sa.insert(questions), to_insert)

        deactivated = 0
        if deactivate_missing:
            in_file = {r["question_id"] for r in records}
            stale = [qid for qid, o in existing.items() if qid not in in_file and o.is_active]
            if stale:
                conn.execute(
                    sa.update(questions)
                    .where(questions.c.question_id.in_(stale))
                    .values(is_active=False, updated_at=now)
                )
                deactivated = len(stale)
    return {"inserted": len(to_insert), "updated": updated, "deactivated": deactivated, "total": len(records)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Load the questions Excel file into the database.")
    ap.add_argument("file", nargs="?", help="Path to .xlsx (default: first .xlsx in data/)")
    ap.add_argument("--keep-missing", action="store_true", help="Do not deactivate questions missing from the file")
    args = ap.parse_args(argv)

    path = Path(args.file) if args.file else next(iter(sorted(DATA_DIR.glob("*.xlsx"))), None)
    if not path or not path.exists():
        print("No Excel file found. Put it in the data/ folder or pass a path.")
        return 1

    print(f"Reading {path.name} ...")
    records, problems = clean(load_excel(path))
    if problems:
        print("Fix these problems in the Excel file first:")
        for p in problems:
            print(" -", p)
        return 1

    engine = make_engine()
    metadata.create_all(engine)
    print(f"Done: {sync(records, engine, deactivate_missing=not args.keep_missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
