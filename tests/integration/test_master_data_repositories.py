"""Integration tests for Customer/Vendor/Part master-data repositories."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.core import Customer, Part, Vendor
from app.repositories.customers import CustomerRepository
from app.repositories.parts import PartRepository
from app.repositories.vendors import VendorRepository


def test_customer_search_matches_code_and_name(db_session: Session) -> None:
    db_session.add(Customer(code="ACME", name="Acme Corp", importance=1))
    db_session.add(Customer(code="ZETA", name="Zeta Industries", importance=3))
    db_session.commit()

    repo = CustomerRepository(db_session)
    rows, total = repo.search("acme")
    assert total == 1
    assert rows[0].code == "ACME"


def test_customer_search_active_only(db_session: Session) -> None:
    db_session.add(Customer(code="A1", name="Active Co", is_active=True))
    db_session.add(Customer(code="I1", name="Inactive Co", is_active=False))
    db_session.commit()

    repo = CustomerRepository(db_session)
    rows, total = repo.search(active_only=True)
    assert total == 1
    assert rows[0].code == "A1"


def test_vendor_search_pagination(db_session: Session) -> None:
    for i in range(5):
        db_session.add(Vendor(code=f"V{i}", name=f"Vendor {i}"))
    db_session.commit()

    repo = VendorRepository(db_session)
    page1, total = repo.search(limit=2, offset=0)
    page2, _ = repo.search(limit=2, offset=2)
    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert {v.code for v in page1}.isdisjoint({v.code for v in page2})


def test_part_search_by_drawing_number(db_session: Session) -> None:
    db_session.add(Part(part_number="P1", revision="A", drawing_number="DWG-9001"))
    db_session.add(Part(part_number="P2", revision="A", drawing_number="DWG-9002"))
    db_session.commit()

    repo = PartRepository(db_session)
    rows, total = repo.search("9001")
    assert total == 1
    assert rows[0].part_number == "P1"


def test_part_natural_key_lookup(db_session: Session) -> None:
    db_session.add(Part(part_number="P3", revision="B"))
    db_session.commit()

    repo = PartRepository(db_session)
    found = repo.get_by_number_revision("P3", "B")
    missing = repo.get_by_number_revision("P3", "A")
    assert found is not None
    assert missing is None
