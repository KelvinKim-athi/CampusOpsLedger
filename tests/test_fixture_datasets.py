from campusops.datasets.fixtures import iter_jsonl_gz, load_default_manifest, summarize_fixture


def test_fixture_manifest_loads_and_verifies():
    manifest = load_default_manifest(".")

    assert manifest.name == "CampusOpsLedger synthetic fixture pack"
    assert manifest.total_records() > 10000
    assert manifest.total_compressed_bytes() > 12_000_000

    result = manifest.verify(".")
    assert result["ok"] is True
    assert result["fixture_count"] == 2


def test_fixture_reader_streams_jsonl_gzip_rows():
    manifest = load_default_manifest(".")
    fixture = manifest.by_domain("import_events")

    rows = list(iter_jsonl_gz(fixture.absolute_path("."), limit=5))

    assert len(rows) == 5
    assert rows[0]["domain"] == "import_events"
    assert rows[0]["event_id"].startswith("import_events-")


def test_fixture_summary_counts_sample_rows():
    manifest = load_default_manifest(".")
    fixture = manifest.by_domain("decision_audit")

    summary = summarize_fixture(fixture.absolute_path("."), sample_limit=200)

    assert summary["sampled"] == 200
    assert sum(summary["status_counts"].values()) == 200
    assert sum(summary["priority_counts"].values()) == 200
