"""
SynCoop backend integration tests.
Covers: demo auth (4 roles), membership/KYC lock, vessels, transactions, quota guardrail,
debts, fish prices, fish calc, admin user mgmt, notifications, role-based access.
"""
import os
import uuid
import pytest
import requests
from pathlib import Path

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        env_files = [
            Path("/app/frontend/.env"),
            Path(__file__).resolve().parents[2] / "frontend" / ".env",
        ]
        for env_file in env_files:
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

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"


# --------------------------- helpers / fixtures ---------------------------
def _demo_session(role: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/demo", json={"role": role}, timeout=15)
    assert r.status_code == 200, f"demo login {role} failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["role"] == role
    return s


@pytest.fixture(scope="session")
def nelayan(): return _demo_session("NELAYAN")
@pytest.fixture(scope="session")
def lapang(): return _demo_session("PETUGAS_LAPANG")
@pytest.fixture(scope="session")
def admin(): return _demo_session("ADMIN")
@pytest.fixture(scope="session")
def dinas(): return _demo_session("PETUGAS_DINAS")


# --------------------------- health / auth ---------------------------
class TestHealthAndAuth:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_demo_login_all_roles(self):
        for role in ["NELAYAN", "PETUGAS_LAPANG", "ADMIN", "PETUGAS_DINAS"]:
            s = _demo_session(role)
            me = s.get(f"{API}/auth/me", timeout=10)
            assert me.status_code == 200
            assert me.json()["role"] == role

    def test_demo_login_invalid_role(self):
        r = requests.post(f"{API}/auth/demo", json={"role": "HACKER"}, timeout=10)
        assert r.status_code == 400

    def test_me_requires_auth(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_logout(self, nelayan):
        # Use ephemeral session to avoid polluting other tests
        s = _demo_session("NELAYAN")
        r = s.post(f"{API}/auth/logout", timeout=10)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=10)
        assert me.status_code == 401


# --------------------------- membership / KYC ---------------------------
class TestMembership:
    def test_status_locked(self, nelayan):
        r = nelayan.get(f"{API}/membership/status", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["is_matured"] is False
        assert d["seconds_remaining"] > 0
        assert d["days_remaining"] > 300

    def test_kyc_locked_until_matured(self, nelayan):
        r = nelayan.post(f"{API}/kyc/submit",
                         json={"nik": "1234567890123456", "phone": "0811", "address": "Bali"},
                         timeout=10)
        assert r.status_code == 403


# --------------------------- vessels ---------------------------
class TestVessels:
    def test_nelayan_sees_own_vessels(self, nelayan):
        r = nelayan.get(f"{API}/vessels", timeout=10)
        assert r.status_code == 200
        vs = r.json()
        assert len(vs) >= 2
        for v in vs:
            assert "remaining_quota" in v and "used_quota" in v
            assert v["monthly_quota_max"] == 400.0

    def test_dinas_create_vessel(self, dinas):
        unique = f"REK/TEST/{uuid.uuid4().hex[:8]}"
        r = dinas.post(f"{API}/vessels", json={
            "owner_email": "nelayan@demo.syncoop.id",
            "vessel_name": "TEST_Vessel",
            "vessel_type": "PAS_KECIL",
            "rekom_number": unique,
        }, timeout=10)
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["rekom_number"] == unique
        # verify appears in list
        listing = dinas.get(f"{API}/vessels", timeout=10).json()
        assert any(x["rekom_number"] == unique for x in listing)

    def test_dinas_create_vessel_duplicate_rekom_rejected(self, dinas):
        unique = f"REK/DUP/{uuid.uuid4().hex[:6]}"
        payload = {"owner_email": "nelayan@demo.syncoop.id", "vessel_name": "T",
                   "vessel_type": "PAS_BESAR", "rekom_number": unique}
        r1 = dinas.post(f"{API}/vessels", json=payload, timeout=10)
        assert r1.status_code == 200
        r2 = dinas.post(f"{API}/vessels", json=payload, timeout=10)
        assert r2.status_code == 400

    def test_nelayan_cannot_create_vessel(self, nelayan):
        r = nelayan.post(f"{API}/vessels", json={
            "owner_email": "nelayan@demo.syncoop.id", "vessel_name": "X",
            "vessel_type": "PAS_KECIL", "rekom_number": f"REK/X/{uuid.uuid4().hex[:6]}",
        }, timeout=10)
        assert r.status_code == 403


# --------------------------- transactions / quota ---------------------------
class TestTransactionsAndQuota:
    def test_lapang_create_lunas(self, lapang, nelayan):
        vs = nelayan.get(f"{API}/vessels", timeout=10).json()
        # pick vessel with highest remaining
        v = max(vs, key=lambda x: x["remaining_quota"])
        liters = 10.0
        total = liters * 6800
        r = lapang.post(f"{API}/transactions", json={
            "vessel_id": v["vessel_id"], "liters_bought": liters, "amount_paid": total,
        }, timeout=10)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["status"] == "LUNAS"
        assert t["remaining_balance"] == 0

    def test_lapang_create_dp_creates_notification(self, lapang, nelayan):
        vs = nelayan.get(f"{API}/vessels", timeout=10).json()
        v = max(vs, key=lambda x: x["remaining_quota"])
        liters = 20.0
        r = lapang.post(f"{API}/transactions", json={
            "vessel_id": v["vessel_id"], "liters_bought": liters, "amount_paid": 1000.0,
        }, timeout=10)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["status"] == "DP"
        assert t["remaining_balance"] > 0
        # nelayan got notification
        notifs = nelayan.get(f"{API}/notifications", timeout=10).json()
        assert any(n.get("type") == "DEBT" for n in notifs["items"])

    def test_quota_hard_block(self, lapang, nelayan):
        vs = nelayan.get(f"{API}/vessels", timeout=10).json()
        v = vs[0]
        r = lapang.post(f"{API}/transactions", json={
            "vessel_id": v["vessel_id"], "liters_bought": 500.0, "amount_paid": 0,
        }, timeout=10)
        assert r.status_code == 400
        detail = r.json().get("detail")
        # FastAPI returns dict detail
        assert isinstance(detail, dict)
        assert detail.get("code") == "QUOTA_EXCEEDED"

    def test_payment_exceeds_total_rejected(self, lapang, nelayan):
        vs = nelayan.get(f"{API}/vessels", timeout=10).json()
        v = max(vs, key=lambda x: x["remaining_quota"])
        r = lapang.post(f"{API}/transactions", json={
            "vessel_id": v["vessel_id"], "liters_bought": 5, "amount_paid": 9999999,
        }, timeout=10)
        assert r.status_code == 400

    def test_nelayan_cannot_create_transaction(self, nelayan):
        vs = nelayan.get(f"{API}/vessels", timeout=10).json()
        r = nelayan.post(f"{API}/transactions", json={
            "vessel_id": vs[0]["vessel_id"], "liters_bought": 5, "amount_paid": 0,
        }, timeout=10)
        assert r.status_code == 403

    def test_admin_validate_transaction(self, admin, lapang, nelayan):
        vs = nelayan.get(f"{API}/vessels", timeout=10).json()
        v = max(vs, key=lambda x: x["remaining_quota"])
        # create
        r = lapang.post(f"{API}/transactions", json={
            "vessel_id": v["vessel_id"], "liters_bought": 5, "amount_paid": 0,
        }, timeout=10)
        assert r.status_code == 200
        trx_id = r.json()["transaction_id"]
        # validate
        rv = admin.post(f"{API}/transactions/{trx_id}/validate",
                        json={"receipt_photo_url": "https://example.com/r.jpg"}, timeout=10)
        assert rv.status_code == 200
        # verify persistence
        listing = admin.get(f"{API}/transactions", timeout=10).json()
        match = next((t for t in listing if t["transaction_id"] == trx_id), None)
        assert match and match["is_validated"] is True
        assert match["receipt_photo_url"] == "https://example.com/r.jpg"

    def test_nelayan_set_debt_reason(self, nelayan, lapang):
        # create DP first
        vs = nelayan.get(f"{API}/vessels", timeout=10).json()
        v = max(vs, key=lambda x: x["remaining_quota"])
        r = lapang.post(f"{API}/transactions", json={
            "vessel_id": v["vessel_id"], "liters_bought": 5, "amount_paid": 0,
        }, timeout=10)
        trx_id = r.json()["transaction_id"]
        rr = nelayan.post(f"{API}/transactions/{trx_id}/debt-reason",
                          json={"reason": "Hasil tangkapan rendah"}, timeout=10)
        assert rr.status_code == 200
        listing = nelayan.get(f"{API}/transactions", timeout=10).json()
        match = next((t for t in listing if t["transaction_id"] == trx_id), None)
        assert match["debt_reason"] == "Hasil tangkapan rendah"

    def test_admin_master_debt_and_reminder(self, admin):
        m = admin.get(f"{API}/debts/master", timeout=10).json()
        assert "total_outstanding" in m and "items" in m
        if m["count"] > 0:
            trx_id = m["items"][0]["transaction_id"]
            r = admin.post(f"{API}/transactions/{trx_id}/remind", timeout=10)
            assert r.status_code == 200


# --------------------------- fish prices + calculator ---------------------------
class TestFishCalculator:
    def test_list_fish_prices(self, nelayan):
        r = nelayan.get(f"{API}/fish-prices", timeout=10)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_admin_create_update_delete_fish(self, admin):
        name = f"TEST_Ikan_{uuid.uuid4().hex[:6]}"
        r = admin.post(f"{API}/fish-prices", json={"name": name, "price_per_kg": 50000}, timeout=10)
        assert r.status_code == 200
        fid = r.json()["fish_id"]
        ru = admin.put(f"{API}/fish-prices/{fid}", json={"name": name, "price_per_kg": 60000}, timeout=10)
        assert ru.status_code == 200
        listing = admin.get(f"{API}/fish-prices", timeout=10).json()
        match = next((f for f in listing if f["fish_id"] == fid), None)
        assert match and match["price_per_kg"] == 60000
        rd = admin.delete(f"{API}/fish-prices/{fid}", timeout=10)
        assert rd.status_code == 200

    def test_nelayan_cannot_create_fish(self, nelayan):
        r = nelayan.post(f"{API}/fish-prices", json={"name": "X", "price_per_kg": 100}, timeout=10)
        assert r.status_code == 403

    def test_profit_sharing_get_update(self, admin):
        r = admin.get(f"{API}/settings/profit-sharing", timeout=10).json()
        assert "profit_sharing_percent" in r
        orig = r["profit_sharing_percent"]
        ru = admin.put(f"{API}/settings/profit-sharing", json={"profit_sharing_percent": 15.0}, timeout=10)
        assert ru.status_code == 200
        nv = admin.get(f"{API}/settings/profit-sharing", timeout=10).json()
        assert nv["profit_sharing_percent"] == 15.0
        admin.put(f"{API}/settings/profit-sharing", json={"profit_sharing_percent": orig}, timeout=10)

    def test_fish_calc_math(self, nelayan):
        fishes = nelayan.get(f"{API}/fish-prices", timeout=10).json()
        f = fishes[0]
        weight = 5.0
        r = nelayan.post(f"{API}/fish-calc",
                        json={"fish_id": f["fish_id"], "weight_kg": weight}, timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        gross = round(weight * f["price_per_kg"], 2)
        cut = round(gross * d["profit_sharing_percent"] / 100, 2)
        net = round(gross - cut, 2)
        assert d["gross"] == gross
        assert d["coop_cut"] == cut
        assert d["net_income"] == net


# --------------------------- admin users ---------------------------
class TestAdminUsers:
    def test_admin_list_users(self, admin):
        r = admin.get(f"{API}/admin/users", timeout=10)
        assert r.status_code == 200
        users = r.json()
        assert any(u["email"] == "nelayan@demo.syncoop.id" for u in users)
        # no pin_hash / _id leaked
        for u in users:
            assert "pin_hash" not in u
            assert "_id" not in u

    def test_nelayan_cannot_list_admin_users(self, nelayan):
        r = nelayan.get(f"{API}/admin/users", timeout=10)
        assert r.status_code == 403

    def test_admin_change_role_and_restore(self, admin):
        users = admin.get(f"{API}/admin/users", timeout=10).json()
        nelayan = next(u for u in users if u["email"] == "nelayan@demo.syncoop.id")
        uid = nelayan["user_id"]
        r = admin.put(f"{API}/admin/users/{uid}/role", json={"role": "PETUGAS_LAPANG"}, timeout=10)
        assert r.status_code == 200
        u2 = next(u for u in admin.get(f"{API}/admin/users", timeout=10).json() if u["user_id"] == uid)
        assert u2["role"] == "PETUGAS_LAPANG"
        # restore
        admin.put(f"{API}/admin/users/{uid}/role", json={"role": "NELAYAN"}, timeout=10)

    def test_admin_invalid_role(self, admin):
        users = admin.get(f"{API}/admin/users", timeout=10).json()
        uid = users[0]["user_id"]
        r = admin.put(f"{API}/admin/users/{uid}/role", json={"role": "HACKER"}, timeout=10)
        assert r.status_code == 400


# --------------------------- dashboard / notifications ---------------------------
class TestDashboardAndNotifs:
    def test_nelayan_dashboard(self, nelayan):
        # Re-login fresh; retry to dodge xdist race with admin role-change test
        import time
        last = None
        for _ in range(5):
            s = requests.Session()
            s.headers.update({"Content-Type": "application/json"})
            body = s.post(f"{API}/auth/demo", json={"role": "NELAYAN"}, timeout=15).json()
            if body.get("role") == "NELAYAN":
                r = s.get(f"{API}/dashboard/stats", timeout=10).json()
                assert r["role"] == "NELAYAN"
                assert r["vessel_count"] >= 2
                return
            last = body
            time.sleep(0.5)
        pytest.fail(f"NELAYAN demo never returned NELAYAN role: {last}")

    def test_admin_dashboard(self, admin):
        r = admin.get(f"{API}/dashboard/stats", timeout=10).json()
        assert r["role"] == "ADMIN"
        for k in ["total_users", "total_vessels", "total_transactions",
                  "pending_validation", "total_outstanding"]:
            assert k in r

    def test_notifications(self, nelayan):
        r = nelayan.get(f"{API}/notifications", timeout=10).json()
        assert "items" in r and "unread" in r
