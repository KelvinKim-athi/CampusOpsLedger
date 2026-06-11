from decimal import Decimal

import pytest

from campusops.assets.inventory import (
    AVAILABLE,
    CLOSED,
    IN_PROGRESS,
    MAINTENANCE,
    Asset,
    AssetRegister,
    MaintenanceTicket,
)
from campusops.catalog.courses import Course, CourseCatalog, CurriculumRule, Programme


def make_catalog():
    catalog = CourseCatalog()
    catalog.add_course(Course("ICT-100", "Computer Fundamentals", 3, "Computing", 1, tags=("core",)))
    catalog.add_course(Course("ICT-110", "Programming One", 4, "Computing", 1, prerequisites=("ICT-100",), tags=("core", "programming")))
    catalog.add_course(Course("ICT-210", "Data Structures", 4, "Computing", 2, prerequisites=("ICT-110",), tags=("core", "programming")))
    catalog.add_course(Course("ICT-220", "Database Systems", 3, "Computing", 2, prerequisites=("ICT-110",), tags=("database",)))
    catalog.add_programme(
        Programme(
            "BIT",
            "Information Technology",
            "Computing",
            4,
            14,
            rules=(
                CurriculumRule("core", "Complete core courses", required_courses=("ICT-100", "ICT-110")),
                CurriculumRule("programming", "Complete programming credits", minimum_credit_units=8, required_tags=("programming",)),
            ),
        )
    )
    return catalog


def test_catalog_prerequisite_chain_and_recommendations():
    catalog = make_catalog()

    assert catalog.prerequisite_chain("ICT-210") == ["ICT_100", "ICT_110"]
    assert [course.code for course in catalog.recommend_next_courses(["ICT-100"])] == ["ICT_110"]
    assert [course.code for course in catalog.recommend_next_courses(["ICT-100", "ICT-110"], tags=["database"])] == ["ICT_220"]


def test_catalog_graduation_audit_and_roundtrip(tmp_path):
    catalog = make_catalog()

    audit = catalog.graduation_audit("BIT", ["ICT-100", "ICT-110", "ICT-210", "ICT-220"])

    assert audit["eligible"] is True
    assert audit["completed_credit_units"] == 14
    assert audit["missing_requirements"] == []

    path = tmp_path / "catalog.json"
    catalog.save_json(path)
    loaded = CourseCatalog.load_json(path)

    assert len(loaded) == 4
    assert loaded.get_programme("bit").name == "Information Technology"


def test_catalog_rejects_unknown_prerequisite():
    catalog = CourseCatalog()

    with pytest.raises(KeyError, match="unknown prerequisite"):
        catalog.add_course(Course("ICT-200", "Advanced", 3, "Computing", 2, prerequisites=("ICT-100",)))


def make_register():
    register = AssetRegister()
    register.add_asset(Asset("LAP-1", "KYU-LAP-001", "HP EliteBook", "Laptop", "120000", "2024-01-01T00:00:00Z", useful_life_months=24))
    register.add_asset(Asset("PRJ-1", "KYU-PRJ-001", "Epson Projector", "Projector", "90000", "2025-01-01T00:00:00Z", useful_life_months=36))
    return register


def test_asset_assignment_release_and_book_value():
    register = make_register()

    assigned = register.assign_asset("lap-1", "ICT Lab", location="Lab 2")
    assert assigned.status == "assigned"
    assert assigned.assigned_to == "ICT Lab"

    released = register.release_asset("lap-1")
    assert released.status == AVAILABLE
    assert released.assigned_to == ""

    value = released.book_value("2025-01-01T00:00:00Z")
    assert value == Decimal("60000.00")


def test_maintenance_ticket_updates_asset_status_and_cost_report():
    register = make_register()
    ticket = register.open_ticket(MaintenanceTicket("T-1", "LAP-1", "Keyboard failure", priority="urgent", reported_by="ICT Lab"))

    assert ticket.status == "open"
    assert register.get_asset("lap-1").status == MAINTENANCE

    register.update_ticket("T-1", IN_PROGRESS, note="Technician assigned")
    closed = register.update_ticket("T-1", CLOSED, note="Keyboard replaced", cost="4500")

    assert closed.cost == Decimal("4500.00")
    assert register.get_asset("lap-1").status == AVAILABLE
    assert register.maintenance_cost_report()["total_cost"] == "4500.00"


def test_asset_register_reports_and_json_roundtrip(tmp_path):
    register = make_register()
    register.assign_asset("PRJ-1", "Lecture Hall")

    report = register.valuation_report("2026-01-01T00:00:00Z")
    assert report["asset_count"] == 2
    assert report["by_category"]["laptop"] == "0.00"
    assert report["by_category"]["projector"] == "60000.00"

    path = tmp_path / "assets.json"
    register.save_json(path)
    loaded = AssetRegister.load_json(path)

    assert len(loaded) == 2
    assert loaded.assigned_to("Lecture Hall")[0].asset_id == "prj_1"
