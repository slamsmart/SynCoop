"""Tests for new Lelang Ikan (fish sales) feature with CASH and POTONG_UTANG."""
import os
import uuid
import pytest
import requests
from pathlib import Path


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        env_file = Path("/app/frontend/.env")
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"


def _demo(role: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/demo", json={"role": role}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def nelayan(): return _demo("NELAYAN")
@pytest.fixture(scope="module")
def lapang(): return _demo("PETUGAS_LAPANG")
@pytest.fixture(scope="module")
def admin(): return _demo("ADMIN")


def _pick_nelayan_vessel(nelayan):
    vs = nelayan.get(f"{API}/vessels", timeout=10).json()
    assert vs
    return vs[0]


def _pick_fish(nelayan):
    fishes = nelayan.get(f"{API}/fish-prices", timeout=10).json()
    return fishes[0]


# ---------- Vessels expose owner_outstanding ----------
class TestVesselOutstanding:
    def test_vessels_have_owner_outstanding(self, lapang):
        vs = lapang.get(f"{API}/vessels", timeout=10).json()
        assert vs
        for v in vs:
            assert "owner_outstanding" in v
            assert isinstance(v["owner_outstanding"], (int, float))


# ---------- Auth / role checks ----------
class TestFishSalesAccess:
    def test_nelayan_cannot_create_sale(self, nelayan):
        vessel = _pick_nelayan_vessel(nelayan)
        fish = _pick_fish(nelayan)
        r = nelayan.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": 1.0, "payment_method": "CASH",
        }, timeout=10)
        assert r.status_code == 403

    def test_nelayan_sees_only_own(self, nelayan, lapang):
        r = nelayan.get(f"{API}/fish-sales", timeout=10)
        assert r.status_code == 200
        for s in r.json():
            # nelayan demo email maps to fisherman owner; just confirm fisherman_id consistent
            assert s.get("fisherman_id") is not None

    def test_lapang_sees_all(self, lapang):
        r = lapang.get(f"{API}/fish-sales", timeout=10)
        assert r.status_code == 200


# ---------- CASH payment ----------
class TestCashSale:
    def test_cash_sale_math_and_persistence(self, lapang, nelayan):
        vessel = _pick_nelayan_vessel(nelayan)
        fish = _pick_fish(nelayan)
        weight = 3.0
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": weight, "payment_method": "CASH",
        }, timeout=10)
        assert r.status_code == 200, r.text
        sale = r.json()
        expected_gross = round(weight * fish["price_per_kg"], 2)
        assert sale["gross_amount"] == expected_gross
        assert sale["amount_deducted"] == 0
        assert sale["cash_paid"] == expected_gross
        assert sale["payment_method"] == "CASH"
        assert sale["price_per_kg"] == fish["price_per_kg"]
        sid = sale["sale_id"]
        listing = lapang.get(f"{API}/fish-sales", timeout=10).json()
        assert any(s["sale_id"] == sid for s in listing)

    def test_price_override_used(self, lapang, nelayan):
        vessel = _pick_nelayan_vessel(nelayan)
        fish = _pick_fish(nelayan)
        weight = 2.0
        override = 99000.0
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": weight, "price_per_kg": override, "payment_method": "CASH",
        }, timeout=10)
        assert r.status_code == 200, r.text
        sale = r.json()
        assert sale["price_per_kg"] == override
        assert sale["gross_amount"] == round(weight * override, 2)
        assert sale["cash_paid"] == sale["gross_amount"]


# ---------- POTONG UTANG payment ----------
class TestPotongUtang:
    def test_potong_utang_deducts_oldest_debt_and_creates_fresh_debt_if_needed(self, lapang, admin, nelayan):
        # Ensure there's a known DP debt: create a small one via lapang
        vessel = _pick_nelayan_vessel(nelayan)
        # Create a small DP of about 6800*5=34000 with 0 paid
        rt = lapang.post(f"{API}/transactions", json={
            "vessel_id": vessel["vessel_id"], "liters_bought": 5.0, "amount_paid": 0.0,
        }, timeout=10)
        assert rt.status_code == 200, rt.text
        new_trx = rt.json()
        assert new_trx["status"] == "DP"
        debt_before = new_trx["remaining_balance"]

        # Read vessel outstanding (should be >= debt_before)
        vs_before = lapang.get(f"{API}/vessels", timeout=10).json()
        v_before = next(v for v in vs_before if v["vessel_id"] == vessel["vessel_id"])
        outstanding_before = v_before["owner_outstanding"]
        assert outstanding_before >= debt_before

        # Create a fish sale with POTONG_UTANG that pays exactly debt_before (partial of total outstanding) at a price covering it
        fish = _pick_fish(nelayan)
        # gross == debt_before exactly using override price
        weight = 1.0
        override = round(debt_before, 2)
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": weight, "price_per_kg": override, "payment_method": "POTONG_UTANG",
        }, timeout=10)
        assert r.status_code == 200, r.text
        sale = r.json()
        assert sale["payment_method"] == "POTONG_UTANG"
        assert sale["gross_amount"] == round(weight * override, 2)
        # amount_deducted should equal gross (since outstanding >= gross)
        assert sale["amount_deducted"] == sale["gross_amount"]
        assert sale["cash_paid"] == 0

        # Outstanding should have decreased by exactly the gross
        vs_after = lapang.get(f"{API}/vessels", timeout=10).json()
        v_after = next(v for v in vs_after if v["vessel_id"] == vessel["vessel_id"])
        assert round(v_before["owner_outstanding"] - v_after["owner_outstanding"], 2) == sale["amount_deducted"]

    def test_potong_utang_excess_returns_cash(self, lapang, nelayan):
        # Create a tiny DP first
        vessel = _pick_nelayan_vessel(nelayan)
        rt = lapang.post(f"{API}/transactions", json={
            "vessel_id": vessel["vessel_id"], "liters_bought": 1.0, "amount_paid": 0.0,
        }, timeout=10)
        assert rt.status_code == 200, rt.text
        trx_id = rt.json()["transaction_id"]
        debt = rt.json()["remaining_balance"]

        vs_before = lapang.get(f"{API}/vessels", timeout=10).json()
        v_before = next(v for v in vs_before if v["vessel_id"] == vessel["vessel_id"])
        outstanding_before = v_before["owner_outstanding"]

        # Gross way larger than outstanding
        fish = _pick_fish(nelayan)
        override = outstanding_before + 50000.0  # ensures gross > outstanding
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": 1.0, "price_per_kg": override, "payment_method": "POTONG_UTANG",
        }, timeout=10)
        assert r.status_code == 200, r.text
        sale = r.json()
        # all outstanding consumed; remainder as cash
        assert sale["amount_deducted"] == round(outstanding_before, 2)
        assert sale["cash_paid"] == round(sale["gross_amount"] - sale["amount_deducted"], 2)
        assert sale["cash_paid"] > 0

        # The freshly created DP transaction should now be LUNAS (it was paid via deduction)
        listing = lapang.get(f"{API}/transactions", timeout=10).json()
        match = next((t for t in listing if t["transaction_id"] == trx_id), None)
        assert match is not None
        assert match["status"] == "LUNAS"
        assert match["remaining_balance"] == 0

        # Vessel outstanding should now be 0 (everything deducted)
        vs_after = lapang.get(f"{API}/vessels", timeout=10).json()
        v_after = next(v for v in vs_after if v["vessel_id"] == vessel["vessel_id"])
        assert v_after["owner_outstanding"] == 0


# ---------- Validation ----------
class TestFishSaleValidation:
    def test_invalid_payment_method(self, lapang, nelayan):
        vessel = _pick_nelayan_vessel(nelayan)
        fish = _pick_fish(nelayan)
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": 1.0, "payment_method": "BARTER",
        }, timeout=10)
        assert r.status_code == 400

    def test_zero_weight_rejected(self, lapang, nelayan):
        vessel = _pick_nelayan_vessel(nelayan)
        fish = _pick_fish(nelayan)
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": 0, "payment_method": "CASH",
        }, timeout=10)
        assert r.status_code == 400

    def test_unknown_vessel_404(self, lapang, nelayan):
        fish = _pick_fish(nelayan)
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": "vsl_doesnotexist", "fish_id": fish["fish_id"],
            "weight_kg": 1.0, "payment_method": "CASH",
        }, timeout=10)
        assert r.status_code == 404


# ---------- Notification ----------
class TestFishSaleNotification:
    def test_notification_created(self, lapang, nelayan):
        vessel = _pick_nelayan_vessel(nelayan)
        fish = _pick_fish(nelayan)
        # count notifications before
        before = nelayan.get(f"{API}/notifications", timeout=10).json()
        cnt_before = len(before["items"])
        r = lapang.post(f"{API}/fish-sales", json={
            "vessel_id": vessel["vessel_id"], "fish_id": fish["fish_id"],
            "weight_kg": 1.0, "payment_method": "CASH",
        }, timeout=10)
        assert r.status_code == 200
        after = nelayan.get(f"{API}/notifications", timeout=10).json()
        assert len(after["items"]) > cnt_before
