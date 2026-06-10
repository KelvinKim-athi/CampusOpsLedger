from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Iterable

from campusops.imports.validation import clean_key


def normalize_header(value: object) -> str:
    return clean_key(value)


def normalize_row(row: dict[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        header = normalize_header(key)
        if not header:
            continue
        normalized[header] = "" if value is None else str(value).strip()
    return normalized


def read_csv_rows(source: str | Path) -> list[dict[str, str]]:
    if isinstance(source, Path) or Path(str(source)).exists():
        text = Path(source).read_text(encoding="utf-8")
    else:
        text = str(source)

    stream = StringIO(text)
    reader = csv.DictReader(stream)
    return [normalize_row(dict(row)) for row in reader]


def required_fields(row: dict[str, str], fields: Iterable[str]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        key = normalize_header(field)
        if not row.get(key):
            missing.append(key)
    return missing


def write_csv_rows(path: str | Path, rows: Iterable[dict[str, object]], *, fieldnames: list[str] | None = None) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    materialized = [dict(row) for row in rows]
    if fieldnames is None:
        fields: list[str] = []
        for row in materialized:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fieldnames = fields

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: row.get(field, "") for field in fieldnames})