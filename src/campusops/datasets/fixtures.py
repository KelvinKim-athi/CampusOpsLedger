from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


@dataclass(frozen=True)
class FixtureInfo:
    path: str
    domain: str
    records: int
    compressed_bytes: int
    sha256: str

    def absolute_path(self, root: str | Path) -> Path:
        return Path(root) / self.path

    def exists(self, root: str | Path) -> bool:
        return self.absolute_path(root).exists()

    def verify_hash(self, root: str | Path) -> bool:
        path = self.absolute_path(root)
        return hashlib.sha256(path.read_bytes()).hexdigest() == self.sha256


@dataclass(frozen=True)
class FixtureManifest:
    name: str
    purpose: str
    format: str
    fixtures: tuple[FixtureInfo, ...]

    @classmethod
    def load(cls, path: str | Path) -> "FixtureManifest":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            name=payload["name"],
            purpose=payload["purpose"],
            format=payload["format"],
            fixtures=tuple(FixtureInfo(**row) for row in payload.get("fixtures", ())),
        )

    def by_domain(self, domain: str) -> FixtureInfo:
        for fixture in self.fixtures:
            if fixture.domain == domain:
                return fixture
        raise KeyError(f"unknown fixture domain: {domain}")

    def total_records(self) -> int:
        return sum(fixture.records for fixture in self.fixtures)

    def total_compressed_bytes(self) -> int:
        return sum(fixture.compressed_bytes for fixture in self.fixtures)

    def verify(self, root: str | Path) -> dict[str, Any]:
        rows = []
        ok = True
        for fixture in self.fixtures:
            exists = fixture.exists(root)
            hash_ok = exists and fixture.verify_hash(root)
            ok = ok and exists and hash_ok
            rows.append(
                {
                    "domain": fixture.domain,
                    "exists": exists,
                    "hash_ok": hash_ok,
                    "records": fixture.records,
                    "compressed_bytes": fixture.compressed_bytes,
                }
            )
        return {
            "ok": ok,
            "fixture_count": len(self.fixtures),
            "total_records": self.total_records(),
            "total_compressed_bytes": self.total_compressed_bytes(),
            "fixtures": rows,
        }


def iter_jsonl_gz(path: str | Path, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
    count = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield json.loads(line)
            count += 1
            if limit is not None and count >= limit:
                break


def summarize_fixture(path: str | Path, *, sample_limit: int = 5000) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    unit_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    sampled = 0

    for row in iter_jsonl_gz(path, limit=sample_limit):
        sampled += 1
        status = str(row.get("status", "unknown"))
        unit = str(row.get("unit", "unknown"))
        priority = str(row.get("priority", "unknown"))

        status_counts[status] = status_counts.get(status, 0) + 1
        unit_counts[unit] = unit_counts.get(unit, 0) + 1
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    return {
        "sampled": sampled,
        "status_counts": dict(sorted(status_counts.items())),
        "unit_counts": dict(sorted(unit_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
    }


def load_default_manifest(root: str | Path = ".") -> FixtureManifest:
    return FixtureManifest.load(Path(root) / "data" / "fixtures" / "manifest.json")
