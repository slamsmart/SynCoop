"""Integration checks for the 6 core cooperative modules."""
import os
import uuid
from pathlib import Path

import requests


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        for env_file in [Path("/app/frontend/.env"), Path(__file__).resolve().parents[2] / "frontend" / ".env"]:
            if not env_file.exists():
                continue
            for line in env_file.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
            if url:
                break
    if not url:
        raise RuntimeError("REACT_APP_BACKEND_URL not configured")
    return url.rstrip("/")


API = f"{_load_backend_url()}/api"


def _demo(role):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/demo", json={"role": role}, timeout=15)
    assert r.status_code == 200, r.text
    return s


def test_public_portal_and_public_ticket():
    r = requests.get(f"{API}/public/portal", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["fish_prices"] >= 1
    assert isinstance(body["announcements"], list)

    suffix = uuid.uuid4().hex[:6]
    r = requests.post(f"{API}/public/tickets", json={
        "contact_name": f"Warga {suffix}",
        "contact_phone": "081200000000",
        "category": "Pendaftaran Anggota",
        "subject": f"Daftar koperasi {suffix}",
        "message": "Saya ingin bertanya cara bergabung.",
    }, timeout=10)
    assert r.status_code == 200
    assert r.json()["ticket_id"].startswith("tic_")


def test_savings_and_loan_workflow():
    admin = _demo("ADMIN")
    nelayan = _demo("NELAYAN")
    suffix = uuid.uuid4().hex[:6]

    r = admin.post(f"{API}/savings", json={
        "member_email": "nelayan@demo.syncoop.id",
        "entry_type": "SUKARELA",
        "direction": "DEPOSIT",
        "amount": 12345,
        "notes": f"test {suffix}",
    }, timeout=10)
    assert r.status_code == 200, r.text

    mine = nelayan.get(f"{API}/savings", timeout=10)
    assert mine.status_code == 200
    assert mine.json()["balance"] >= 12345

    r = nelayan.post(f"{API}/loans", json={
        "amount": 250000,
        "purpose": f"Modal jaring {suffix}",
        "tenor_months": 3,
    }, timeout=10)
    assert r.status_code == 200, r.text
    loan_id = r.json()["loan_id"]

    r = admin.post(f"{API}/loans/{loan_id}/approve", json={"notes": "ok"}, timeout=10)
    assert r.status_code == 200, r.text
    r = admin.post(f"{API}/loans/{loan_id}/payments", json={"amount": 50000, "payment_method": "CASH"}, timeout=10)
    assert r.status_code == 200, r.text

    loans = nelayan.get(f"{API}/loans", timeout=10).json()["items"]
    matched = next(x for x in loans if x["loan_id"] == loan_id)
    assert matched["outstanding_balance"] == 200000


def test_inventory_and_reports_csv():
    admin = _demo("ADMIN")
    suffix = uuid.uuid4().hex[:6]
    item = admin.post(f"{API}/inventory/items", json={
        "name": f"Es Test {suffix}",
        "category": "Operasional",
        "unit": "balok",
        "min_stock": 2,
    }, timeout=10)
    assert item.status_code == 200, item.text
    item_id = item.json()["item_id"]

    r = admin.post(f"{API}/inventory/movements", json={
        "item_id": item_id,
        "movement_type": "IN",
        "quantity": 5,
        "reason": "Stok awal test",
    }, timeout=10)
    assert r.status_code == 200, r.text

    r = admin.post(f"{API}/inventory/movements", json={
        "item_id": item_id,
        "movement_type": "OUT",
        "quantity": 99,
        "reason": "Tidak boleh negatif",
    }, timeout=10)
    assert r.status_code == 400

    summary = admin.get(f"{API}/reports/summary", timeout=10)
    assert summary.status_code == 200
    assert "net_cash" in summary.json()

    csv_res = admin.get(f"{API}/reports/inventory.csv", timeout=10)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
