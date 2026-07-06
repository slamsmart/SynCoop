import os
import logging
import csv
import io
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode, urlparse

import requests
from fastapi import (
    FastAPI, APIRouter, HTTPException, Request, Response, Depends,
    UploadFile, File, Header, Query,
)
from starlette.middleware.cors import CORSMiddleware

from database import (
    db, users, sessions, vessels, transactions, fish_prices, fish_calcs,
    fish_sales, notifications, settings, savings_entries, loans, loan_payments,
    inventory_items, inventory_movements, service_tickets, ticket_messages,
    announcements,
)
from starlette.responses import RedirectResponse
import storage as objstore
from models import (
    User, DemoLogin, KycSubmit, VesselCreate, Vessel,
    Transaction, TransactionCreate, ValidateTransaction, DebtReason, FishPriceCreate,
    FishCalcRequest, ProfitSharing, PublicPortalSettings, RoleUpdate, FishSaleCreate, now_utc, gen_id,
    SavingsEntryCreate, LoanCreate, LoanDecision, LoanPaymentCreate,
    InventoryItemCreate, InventoryMovementCreate, ServiceTicketCreate,
    TicketReplyCreate, TicketStatusUpdate, AnnouncementCreate,
)
from deps import get_current_user, require_roles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("syncoop")

MATURATION_DAYS = 365
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_OAUTH_REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
DEFAULT_BBM_PRICE = 6800.0
DEFAULT_PROFIT_SHARING = 10.0
DEFAULT_PUBLIC_STAT_CARDS = [
    {"key": "members", "label": "Anggota Bergabung", "icon": "Users"},
    {"key": "transaction_value", "label": "Perputaran Transaksi", "icon": "ReceiptText"},
    {"key": "fuel_liters", "label": "Penyaluran BBM Kapal Nelayan", "icon": "Fuel"},
    {"key": "vessels", "label": "Kapal Rekom BBM", "icon": "Ship"},
]
DEFAULT_PUBLIC_PORTAL = {
    "hero_kicker": "Ekosistem Manajemen Koperasi Nelayan",
    "hero_heading": "Koperasi nelayan yang transparan dan dekat.",
    "hero_description": "Kelola BBM subsidi & kas koperasi secara transparan. Distribusi BBM tepat sasaran, kalkulator hasil tangkapan, dan pembukuan utang yang adil untuk nelayan akar rumput.",
    "stat_cards": DEFAULT_PUBLIC_STAT_CARDS,
}
PAYMENT_METHODS = ("CASH", "QRIS", "TRANSFER", "PIUTANG", "POTONG_UTANG")

app = FastAPI()
api = APIRouter(prefix="/api")


# ----------------------------- helpers -----------------------------
def public_user(u: dict) -> dict:
    u.pop("pin_hash", None)
    u.pop("biometric_credential_id", None)
    u.pop("biometric_enabled", None)
    u.pop("biometric_device_name", None)
    u.pop("biometric_registered_at", None)
    u.pop("_id", None)
    return u


def month_key(dt: datetime = None) -> str:
    dt = dt or now_utc()
    return dt.strftime("%Y-%m")


async def get_setting(key: str, default):
    doc = await settings.find_one({"key": key}, {"_id": 0})
    return doc["value"] if doc else default

async def get_public_portal_settings() -> dict:
    value = await get_setting("public_portal", DEFAULT_PUBLIC_PORTAL)
    merged = {**DEFAULT_PUBLIC_PORTAL, **(value or {})}
    merged["stat_cards"] = normalize_stat_cards(merged.get("stat_cards"))
    return merged

def normalize_stat_cards(cards) -> list:
    allowed = {card["key"]: card for card in DEFAULT_PUBLIC_STAT_CARDS}
    incoming = {
        card.get("key"): card
        for card in (cards or [])
        if isinstance(card, dict) and card.get("key") in allowed
    }
    normalized = []
    for default in DEFAULT_PUBLIC_STAT_CARDS:
        card = incoming.get(default["key"], {})
        normalized.append({
            "key": default["key"],
            "label": (card.get("label") or default["label"]).strip(),
            "icon": (card.get("icon") or default["icon"]).strip(),
        })
    return normalized


async def create_session(user_id: str, role: str | None = None) -> str:
    token = gen_id("sess") + gen_id("t")
    expires = now_utc() + timedelta(days=7)
    doc = {
        "user_id": user_id,
        "session_token": token,
        "expires_at": expires.isoformat(),
        "created_at": now_utc().isoformat(),
    }
    if role:
        doc["role"] = role
    await sessions.insert_one(doc)
    return token


def local_frontend_url() -> bool:
    host = urlparse(FRONTEND_URL).hostname
    return host in {"localhost", "127.0.0.1"}


def insecure_local_cookie() -> bool:
    return os.environ.get("APP_ENV", "local") == "local" and local_frontend_url()


def set_session_cookie(response: Response, token: str):
    insecure_local = insecure_local_cookie()
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=not insecure_local,
        samesite="lax" if insecure_local else "none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )


def set_short_lived_cookie(response: Response, key: str, value: str, max_age: int = 600):
    insecure_local = insecure_local_cookie()
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=not insecure_local,
        samesite="lax" if insecure_local else "none",
        path="/",
        max_age=max_age,
    )

def safe_frontend_path(path: str = None) -> str:
    if not path or not path.startswith("/") or path.startswith("//"):
        return "/dashboard"
    return path

def frontend_redirect_url(path: str = None) -> str:
    return f"{FRONTEND_URL}{safe_frontend_path(path)}"

def google_redirect_uri(request: Request) -> str:
    if GOOGLE_OAUTH_REDIRECT_URI:
        return GOOGLE_OAUTH_REDIRECT_URI
    return str(request.url_for("google_callback"))

def google_oauth_ready() -> bool:
    return bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

async def new_user_doc(email: str, name: str, picture: str = None, role: str = "NELAYAN") -> dict:
    created = now_utc()
    return {
        "user_id": gen_id("user"),
        "email": email,
        "name": name,
        "picture": picture,
        "role": role,
        "created_at": created.isoformat(),
        "maturation_end_date": (created + timedelta(days=MATURATION_DAYS)).isoformat(),
        "is_kyc_approved": False,
        "kyc_status": "NONE",
        "phone": None, "nik": None, "address": None,
    }


async def add_notification(user_id: str, message: str, ntype: str = "INFO", related=None):
    await notifications.insert_one({
        "notif_id": gen_id("ntf"), "user_id": user_id, "message": message,
        "type": ntype, "related_transaction_id": related, "is_read": False,
        "created_at": now_utc().isoformat(),
    })

async def disable_legacy_biometric_flags():
    await users.update_many(
        {
            "$or": [
                {"biometric_enabled": {"$exists": True}},
                {"biometric_credential_id": {"$exists": True}},
                {"biometric_device_name": {"$exists": True}},
                {"biometric_registered_at": {"$exists": True}},
            ]
        },
        {
            "$set": {"biometric_enabled": False},
            "$unset": {
                "biometric_credential_id": "",
                "biometric_device_name": "",
                "biometric_registered_at": "",
            },
        },
    )

async def find_member_by_email(email: str) -> dict:
    member = await users.find_one({"email": email}, {"_id": 0})
    if not member:
        raise HTTPException(status_code=404, detail="Anggota tidak ditemukan")
    return member

def clean_doc(doc: dict) -> dict:
    if doc:
        doc.pop("_id", None)
    return doc

def parse_period(start: str = None, end: str = None):
    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if start else datetime(1970, 1, 1, tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if end else now_utc() + timedelta(days=1)
    return start_dt.isoformat(), end_dt.isoformat()

def csv_response(filename: str, rows: list, fields: list):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ----------------------------- auth -----------------------------
@api.get("/auth/google/start")
async def google_start(request: Request, redirect: str = Query("/dashboard")):
    if not google_oauth_ready():
        raise HTTPException(status_code=503, detail="Google OAuth belum dikonfigurasi")

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": google_redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    response = RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}",
        status_code=302,
    )
    set_short_lived_cookie(response, "oauth_state", state)
    set_short_lived_cookie(response, "oauth_redirect", safe_frontend_path(redirect))
    return response

@api.get("/auth/google/callback")
async def google_callback(request: Request, code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    if error:
        logger.error(f"google oauth error: {error}")
        return RedirectResponse(frontend_redirect_url("/login?oauth=error"), status_code=302)
    if not code or not state or state != request.cookies.get("oauth_state"):
        return RedirectResponse(frontend_redirect_url("/login?oauth=state"), status_code=302)

    try:
        token_res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": google_redirect_uri(request),
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        token_res.raise_for_status()
        token_data = token_res.json()
        user_res = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
            timeout=15,
        )
        user_res.raise_for_status()
        data = user_res.json()
    except Exception as e:
        logger.error(f"google oauth exchange failed: {e}")
        return RedirectResponse(frontend_redirect_url("/login?oauth=failed"), status_code=302)

    email = data.get("email")
    if not email or data.get("email_verified") is False:
        return RedirectResponse(frontend_redirect_url("/login?oauth=email"), status_code=302)

    user = await users.find_one({"email": email}, {"_id": 0})
    if not user:
        user = await new_user_doc(email, data.get("name", email), data.get("picture"))
        await users.insert_one(dict(user))
    token = await create_session(user["user_id"], user.get("role"))
    response = RedirectResponse(frontend_redirect_url(request.cookies.get("oauth_redirect")), status_code=302)
    set_session_cookie(response, token)
    response.delete_cookie("oauth_state", path="/")
    response.delete_cookie("oauth_redirect", path="/")
    return response


@api.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return public_user(dict(user))


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@api.post("/auth/demo")
async def demo_login(body: DemoLogin, response: Response):
    role = body.role.upper()
    mapping = {
        "NELAYAN": ("nelayan@demo.syncoop.id", "Budi Santoso (Nelayan)"),
        "PETUGAS_LAPANG": ("lapang@demo.syncoop.id", "Andi Petugas Lapang"),
        "ADMIN": ("admin@demo.syncoop.id", "Sri Admin Koperasi"),
        "PETUGAS_DINAS": ("dinas@demo.syncoop.id", "Dewi Petugas Dinas"),
    }
    if role not in mapping:
        raise HTTPException(status_code=400, detail="Peran tidak valid")
    email, name = mapping[role]
    user = await users.find_one({"email": email}, {"_id": 0})
    if not user:
        user = await new_user_doc(email, name, role=role)
        await users.insert_one(dict(user))
    session_user = {**user, "role": role}
    token = await create_session(user["user_id"], role)
    set_session_cookie(response, token)
    return public_user(session_user)


# ----------------------------- membership / KYC -----------------------------
@api.get("/membership/status")
async def membership_status(user: dict = Depends(get_current_user)):
    end = datetime.fromisoformat(user["maturation_end_date"])
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    now = now_utc()
    remaining = (end - now).total_seconds()
    is_matured = remaining <= 0
    created = datetime.fromisoformat(user["created_at"])
    total = MATURATION_DAYS * 86400
    elapsed = max(0, total - max(0, remaining))
    return {
        "maturation_end_date": user["maturation_end_date"],
        "created_at": user["created_at"],
        "seconds_remaining": max(0, int(remaining)),
        "days_remaining": max(0, int(remaining // 86400)),
        "is_matured": is_matured,
        "progress_percent": round(min(100, (elapsed / total) * 100), 2),
        "kyc_status": user.get("kyc_status", "NONE"),
        "is_kyc_approved": user.get("is_kyc_approved", False),
    }


@api.post("/kyc/submit")
async def kyc_submit(body: KycSubmit, user: dict = Depends(get_current_user)):
    end = datetime.fromisoformat(user["maturation_end_date"])
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if (end - now_utc()).total_seconds() > 0:
        raise HTTPException(status_code=403,
                            detail="KYC terkunci hingga masa tunggu 365 hari selesai")
    await users.update_one({"user_id": user["user_id"]}, {"$set": {
        "nik": body.nik, "phone": body.phone, "address": body.address,
        "kyc_status": "PENDING",
    }})
    return {"ok": True, "kyc_status": "PENDING"}


# ----------------------------- vessels (Dinas) -----------------------------
@api.post("/vessels", response_model=Vessel)
async def create_vessel(body: VesselCreate, user: dict = Depends(require_roles("PETUGAS_DINAS", "ADMIN"))):
    if body.vessel_type not in ("PAS_BESAR", "PAS_KECIL"):
        raise HTTPException(status_code=400, detail="Jenis pas tidak valid")
    if await vessels.find_one({"rekom_number": body.rekom_number}):
        raise HTTPException(status_code=400, detail="Nomor surat rekomendasi sudah terdaftar")
    owner = await users.find_one({"email": body.owner_email}, {"_id": 0})
    if not owner:
        raise HTTPException(status_code=404, detail="Nelayan dengan email tersebut tidak ditemukan")
    doc = {
        "vessel_id": gen_id("vsl"), "owner_id": owner["user_id"],
        "owner_name": owner["name"], "owner_email": owner["email"],
        "vessel_name": body.vessel_name, "vessel_type": body.vessel_type,
        "rekom_number": body.rekom_number, "monthly_quota_max": 400.0,
        "created_by": user["name"], "created_at": now_utc().isoformat(),
    }
    await vessels.insert_one(dict(doc))
    return Vessel(**doc)


@api.get("/vessels")
async def list_vessels(user: dict = Depends(get_current_user)):
    q = {} if user["role"] in ("PETUGAS_DINAS", "ADMIN", "PETUGAS_LAPANG") else {"owner_id": user["user_id"]}
    docs = await vessels.find(q, {"_id": 0}).to_list(1000)
    for d in docs:
        d["used_quota"] = await _vessel_used(d["vessel_id"])
        d["remaining_quota"] = max(0, d["monthly_quota_max"] - d["used_quota"])
        owner_debts = await transactions.find(
            {"fisherman_id": d["owner_id"], "status": "DP", "remaining_balance": {"$gt": 0}},
            {"_id": 0, "remaining_balance": 1}).to_list(1000)
        d["owner_outstanding"] = round(sum(x["remaining_balance"] for x in owner_debts), 2)
    return docs


async def _vessel_used(vessel_id: str) -> float:
    mk = month_key()
    docs = await transactions.find({"vessel_id": vessel_id, "month_key": mk}, {"_id": 0, "liters_bought": 1}).to_list(1000)
    return round(sum(d["liters_bought"] for d in docs), 2)


# ----------------------------- transactions -----------------------------
@api.post("/transactions", response_model=Transaction)
async def create_transaction(body: TransactionCreate,
                             user: dict = Depends(require_roles("PETUGAS_LAPANG", "ADMIN"))):
    vessel = await vessels.find_one({"vessel_id": body.vessel_id}, {"_id": 0})
    if not vessel:
        raise HTTPException(status_code=404, detail="Perahu tidak ditemukan")
    if body.liters_bought <= 0:
        raise HTTPException(status_code=400, detail="Volume harus lebih dari 0")
    if body.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Metode pembayaran tidak valid")

    used = await _vessel_used(body.vessel_id)
    remaining = vessel["monthly_quota_max"] - used
    if body.liters_bought > remaining:
        raise HTTPException(status_code=400, detail={
            "code": "QUOTA_EXCEEDED",
            "message": f"Kuota bulan ini terlampaui. Sisa kuota {remaining:.0f} L, diminta {body.liters_bought:.0f} L.",
            "used": used, "remaining": max(0, remaining), "max": vessel["monthly_quota_max"],
        })

    price = float(await get_setting("bbm_price_per_liter", DEFAULT_BBM_PRICE))
    total = round(body.liters_bought * price, 2)
    paid = round(body.amount_paid, 2)
    if paid > total:
        raise HTTPException(status_code=400, detail="Pembayaran melebihi total harga")
    remaining_balance = round(total - paid, 2)
    status = "LUNAS" if remaining_balance <= 0 else "DP"

    doc = {
        "transaction_id": gen_id("trx"), "vessel_id": vessel["vessel_id"],
        "vessel_name": vessel["vessel_name"], "fisherman_id": vessel["owner_id"],
        "fisherman_name": vessel["owner_name"], "liters_bought": body.liters_bought,
        "price_per_liter": price, "total_price": total, "amount_paid": paid,
        "payment_method": body.payment_method, "payment_ref": body.payment_ref,
        "status": status, "remaining_balance": remaining_balance,
        "receipt_photo_url": None, "is_validated": False,
        "recorded_by": user["user_id"], "recorded_by_name": user["name"],
        "validated_by": None, "debt_reason": None, "month_key": month_key(),
        "created_at": now_utc().isoformat(),
    }
    await transactions.insert_one(dict(doc))
    if status == "DP":
        await add_notification(vessel["owner_id"],
                               f"Transaksi {body.liters_bought:.0f}L tercatat dengan kurang bayar Rp{remaining_balance:,.0f}. Mohon isi alasan penundaan.",
                               "DEBT", doc["transaction_id"])
    return Transaction(**doc)


@api.get("/transactions")
async def list_transactions(user: dict = Depends(get_current_user)):
    if user["role"] in ("ADMIN", "PETUGAS_LAPANG", "PETUGAS_DINAS"):
        q = {}
    else:
        q = {"fisherman_id": user["user_id"]}
    docs = await transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return docs


@api.post("/transactions/{trx_id}/validate")
async def validate_transaction(trx_id: str, body: ValidateTransaction,
                              user: dict = Depends(require_roles("ADMIN"))):
    trx = await transactions.find_one({"transaction_id": trx_id})
    if not trx:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    await transactions.update_one({"transaction_id": trx_id}, {"$set": {
        "is_validated": True, "receipt_photo_url": body.receipt_photo_url,
        "validated_by": user["name"],
    }})
    await add_notification(trx["fisherman_id"],
                           f"Transaksi BBM {trx['liters_bought']:.0f}L telah divalidasi koperasi.", "INFO", trx_id)
    return {"ok": True}


@api.post("/transactions/{trx_id}/debt-reason")
async def set_debt_reason(trx_id: str, body: DebtReason, user: dict = Depends(get_current_user)):
    trx = await transactions.find_one({"transaction_id": trx_id})
    if not trx:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    if trx["fisherman_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Bukan transaksi Anda")
    await transactions.update_one({"transaction_id": trx_id},
                                  {"$set": {"debt_reason": body.reason}})
    return {"ok": True}


@api.post("/transactions/{trx_id}/remind")
async def remind_debt(trx_id: str, user: dict = Depends(require_roles("ADMIN"))):
    trx = await transactions.find_one({"transaction_id": trx_id})
    if not trx:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    await add_notification(trx["fisherman_id"],
                           f"PENGINGAT: Sisa kurang bayar BBM Rp{trx['remaining_balance']:,.0f} mohon segera dilunasi.",
                           "REMINDER", trx_id)
    return {"ok": True}


@api.get("/debts/master")
async def debts_master(user: dict = Depends(require_roles("ADMIN", "PETUGAS_LAPANG"))):
    docs = await transactions.find({"status": "DP", "remaining_balance": {"$gt": 0}},
                                   {"_id": 0}).sort("created_at", -1).to_list(1000)
    total_outstanding = round(sum(d["remaining_balance"] for d in docs), 2)
    return {"items": docs, "total_outstanding": total_outstanding, "count": len(docs)}

# ----------------------------- savings / loans -----------------------------
@api.get("/savings")
async def list_savings(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "ADMIN" else {"member_id": user["user_id"]}
    items = await savings_entries.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    balance = 0.0
    for item in items:
        signed = item["amount"] if item["direction"] == "DEPOSIT" else -item["amount"]
        balance = round(balance + signed, 2)
    return {"items": items, "balance": balance, "count": len(items)}

@api.post("/savings")
async def create_savings_entry(body: SavingsEntryCreate, user: dict = Depends(require_roles("ADMIN"))):
    if body.entry_type not in ("POKOK", "WAJIB", "SUKARELA"):
        raise HTTPException(status_code=400, detail="Jenis simpanan tidak valid")
    if body.direction not in ("DEPOSIT", "WITHDRAWAL"):
        raise HTTPException(status_code=400, detail="Arah simpanan tidak valid")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari 0")
    member = await find_member_by_email(body.member_email)
    doc = {
        "entry_id": gen_id("sav"), "member_id": member["user_id"], "member_name": member["name"],
        "member_email": member["email"], "entry_type": body.entry_type, "direction": body.direction,
        "amount": round(body.amount, 2), "notes": body.notes, "recorded_by": user["user_id"],
        "recorded_by_name": user["name"], "created_at": now_utc().isoformat(),
    }
    await savings_entries.insert_one(doc)
    await add_notification(member["user_id"], f"Simpanan {body.entry_type.lower()} tercatat Rp{body.amount:,.0f}.", "INFO")
    return clean_doc(doc)

@api.get("/loans")
async def list_loans(user: dict = Depends(get_current_user)):
    q = {} if user["role"] == "ADMIN" else {"member_id": user["user_id"]}
    items = await loans.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    payments_q = {} if user["role"] == "ADMIN" else {"member_id": user["user_id"]}
    payments = await loan_payments.find(payments_q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    outstanding = round(sum(l.get("outstanding_balance", 0) for l in items if l["status"] in ("APPROVED", "DISBURSED")), 2)
    return {"items": items, "payments": payments, "outstanding": outstanding, "count": len(items)}

@api.post("/loans")
async def create_loan(body: LoanCreate, user: dict = Depends(get_current_user)):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal pinjaman harus lebih dari 0")
    if body.tenor_months <= 0:
        raise HTTPException(status_code=400, detail="Tenor harus lebih dari 0")
    member = user
    if user["role"] == "ADMIN" and body.member_email:
        member = await find_member_by_email(body.member_email)
    doc = {
        "loan_id": gen_id("loan"), "member_id": member["user_id"], "member_name": member["name"],
        "member_email": member["email"], "amount": round(body.amount, 2), "purpose": body.purpose,
        "tenor_months": body.tenor_months, "status": "PENDING", "outstanding_balance": 0.0,
        "approved_by": None, "approved_at": None, "decision_notes": None,
        "created_at": now_utc().isoformat(),
    }
    await loans.insert_one(doc)
    return clean_doc(doc)

@api.post("/loans/{loan_id}/approve")
async def approve_loan(loan_id: str, body: LoanDecision, user: dict = Depends(require_roles("ADMIN"))):
    loan = await loans.find_one({"loan_id": loan_id})
    if not loan:
        raise HTTPException(status_code=404, detail="Pinjaman tidak ditemukan")
    await loans.update_one({"loan_id": loan_id}, {"$set": {
        "status": "APPROVED", "outstanding_balance": loan["amount"],
        "approved_by": user["name"], "approved_at": now_utc().isoformat(),
        "decision_notes": body.notes,
    }})
    await add_notification(loan["member_id"], f"Pengajuan pinjaman Rp{loan['amount']:,.0f} disetujui.", "INFO")
    return {"ok": True}

@api.post("/loans/{loan_id}/reject")
async def reject_loan(loan_id: str, body: LoanDecision, user: dict = Depends(require_roles("ADMIN"))):
    loan = await loans.find_one({"loan_id": loan_id})
    if not loan:
        raise HTTPException(status_code=404, detail="Pinjaman tidak ditemukan")
    await loans.update_one({"loan_id": loan_id}, {"$set": {
        "status": "REJECTED", "decision_notes": body.notes,
        "approved_by": user["name"], "approved_at": now_utc().isoformat(),
    }})
    await add_notification(loan["member_id"], "Pengajuan pinjaman belum dapat disetujui.", "INFO")
    return {"ok": True}

@api.post("/loans/{loan_id}/payments")
async def create_loan_payment(loan_id: str, body: LoanPaymentCreate, user: dict = Depends(require_roles("ADMIN"))):
    loan = await loans.find_one({"loan_id": loan_id})
    if not loan:
        raise HTTPException(status_code=404, detail="Pinjaman tidak ditemukan")
    if loan["status"] not in ("APPROVED", "DISBURSED"):
        raise HTTPException(status_code=400, detail="Pinjaman belum aktif")
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal pembayaran harus lebih dari 0")
    pay = min(round(body.amount, 2), round(loan.get("outstanding_balance", 0), 2))
    new_balance = round(loan.get("outstanding_balance", 0) - pay, 2)
    doc = {
        "payment_id": gen_id("lpay"), "loan_id": loan_id, "member_id": loan["member_id"],
        "member_name": loan["member_name"], "amount": pay, "payment_method": body.payment_method,
        "payment_ref": body.payment_ref, "notes": body.notes, "recorded_by": user["user_id"],
        "recorded_by_name": user["name"], "created_at": now_utc().isoformat(),
    }
    await loan_payments.insert_one(doc)
    await loans.update_one({"loan_id": loan_id}, {"$set": {
        "outstanding_balance": new_balance,
        "status": "PAID" if new_balance <= 0 else "DISBURSED",
    }})
    await add_notification(loan["member_id"], f"Cicilan pinjaman tercatat Rp{pay:,.0f}.", "INFO")
    return clean_doc(doc)

# ----------------------------- inventory -----------------------------
@api.get("/inventory/items")
async def list_inventory_items(user: dict = Depends(get_current_user)):
    items = await inventory_items.find({}, {"_id": 0}).sort("name", 1).to_list(1000)
    return {"items": items, "count": len(items)}

@api.post("/inventory/items")
async def create_inventory_item(body: InventoryItemCreate, user: dict = Depends(require_roles("ADMIN"))):
    if body.min_stock < 0:
        raise HTTPException(status_code=400, detail="Stok minimum tidak valid")
    doc = {
        "item_id": gen_id("itm"), "name": body.name, "category": body.category,
        "unit": body.unit, "stock": 0.0, "min_stock": body.min_stock,
        "created_by": user["name"], "created_at": now_utc().isoformat(),
    }
    await inventory_items.insert_one(doc)
    return clean_doc(doc)

@api.get("/inventory/movements")
async def list_inventory_movements(user: dict = Depends(require_roles("ADMIN", "PETUGAS_LAPANG"))):
    items = await inventory_movements.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"items": items, "count": len(items)}

@api.post("/inventory/movements")
async def create_inventory_movement(body: InventoryMovementCreate, user: dict = Depends(require_roles("ADMIN", "PETUGAS_LAPANG"))):
    if body.movement_type not in ("IN", "OUT"):
        raise HTTPException(status_code=400, detail="Jenis mutasi tidak valid")
    if body.quantity <= 0:
        raise HTTPException(status_code=400, detail="Jumlah harus lebih dari 0")
    item = await inventory_items.find_one({"item_id": body.item_id})
    if not item:
        raise HTTPException(status_code=404, detail="Barang tidak ditemukan")
    signed = body.quantity if body.movement_type == "IN" else -body.quantity
    new_stock = round(item.get("stock", 0) + signed, 2)
    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Stok tidak boleh negatif")
    doc = {
        "movement_id": gen_id("mov"), "item_id": item["item_id"], "item_name": item["name"],
        "movement_type": body.movement_type, "quantity": body.quantity, "unit": item["unit"],
        "stock_after": new_stock, "reason": body.reason, "reference": body.reference,
        "recorded_by": user["user_id"], "recorded_by_name": user["name"],
        "created_at": now_utc().isoformat(),
    }
    await inventory_movements.insert_one(doc)
    await inventory_items.update_one({"item_id": item["item_id"]}, {"$set": {"stock": new_stock}})
    return clean_doc(doc)

@api.get("/inventory/alerts")
async def inventory_alerts(user: dict = Depends(require_roles("ADMIN", "PETUGAS_LAPANG"))):
    items = await inventory_items.find({}, {"_id": 0}).to_list(1000)
    low = [i for i in items if i.get("stock", 0) <= i.get("min_stock", 0)]
    return {"items": low, "count": len(low)}


# ----------------------------- fish calculator -----------------------------
@api.get("/fish-prices")
async def list_fish_prices(user: dict = Depends(get_current_user)):
    return await fish_prices.find({}, {"_id": 0}).sort("name", 1).to_list(1000)


@api.post("/fish-prices")
async def create_fish_price(body: FishPriceCreate, user: dict = Depends(require_roles("ADMIN"))):
    doc = {"fish_id": gen_id("fsh"), "name": body.name, "price_per_kg": body.price_per_kg}
    await fish_prices.insert_one(dict(doc))
    return doc


@api.put("/fish-prices/{fish_id}")
async def update_fish_price(fish_id: str, body: FishPriceCreate, user: dict = Depends(require_roles("ADMIN"))):
    res = await fish_prices.update_one({"fish_id": fish_id},
                                       {"$set": {"name": body.name, "price_per_kg": body.price_per_kg}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Jenis ikan tidak ditemukan")
    return {"ok": True}


@api.delete("/fish-prices/{fish_id}")
async def delete_fish_price(fish_id: str, user: dict = Depends(require_roles("ADMIN"))):
    await fish_prices.delete_one({"fish_id": fish_id})
    return {"ok": True}


@api.get("/settings/profit-sharing")
async def get_profit_sharing(user: dict = Depends(get_current_user)):
    val = await get_setting("profit_sharing_percent", DEFAULT_PROFIT_SHARING)
    bbm = await get_setting("bbm_price_per_liter", DEFAULT_BBM_PRICE)
    return {"profit_sharing_percent": val, "bbm_price_per_liter": bbm}


@api.put("/settings/profit-sharing")
async def set_profit_sharing(body: ProfitSharing, user: dict = Depends(require_roles("ADMIN"))):
    await settings.update_one({"key": "profit_sharing_percent"},
                              {"$set": {"value": body.profit_sharing_percent}}, upsert=True)
    return {"ok": True}


@api.get("/settings/public-portal")
async def get_public_portal_config(user: dict = Depends(require_roles("ADMIN"))):
    return await get_public_portal_settings()

@api.put("/settings/public-portal")
async def update_public_portal_config(body: PublicPortalSettings, user: dict = Depends(require_roles("ADMIN"))):
    value = {
        "hero_kicker": body.hero_kicker.strip() or DEFAULT_PUBLIC_PORTAL["hero_kicker"],
        "hero_heading": body.hero_heading.strip() or DEFAULT_PUBLIC_PORTAL["hero_heading"],
        "hero_description": body.hero_description.strip() or DEFAULT_PUBLIC_PORTAL["hero_description"],
        "stat_cards": normalize_stat_cards(body.stat_cards),
    }
    await settings.update_one({"key": "public_portal"}, {"$set": {"value": value}}, upsert=True)
    return value

@api.post("/fish-calc")
async def fish_calc(body: FishCalcRequest, user: dict = Depends(get_current_user)):
    fish = await fish_prices.find_one({"fish_id": body.fish_id}, {"_id": 0})
    if not fish:
        raise HTTPException(status_code=404, detail="Jenis ikan tidak ditemukan")
    percent = float(await get_setting("profit_sharing_percent", DEFAULT_PROFIT_SHARING))
    gross = round(body.weight_kg * fish["price_per_kg"], 2)
    coop_cut = round(gross * percent / 100, 2)
    net = round(gross - coop_cut, 2)
    rec = {
        "calc_id": gen_id("clc"), "user_id": user["user_id"], "fish_name": fish["name"],
        "weight_kg": body.weight_kg, "price_per_kg": fish["price_per_kg"], "gross": gross,
        "profit_sharing_percent": percent, "coop_cut": coop_cut, "net_income": net,
        "created_at": now_utc().isoformat(),
    }
    await fish_calcs.insert_one(dict(rec))
    rec.pop("_id", None)
    return rec


@api.get("/fish-calc/history")
async def fish_calc_history(user: dict = Depends(get_current_user)):
    return await fish_calcs.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)


# ----------------------------- fish sales / auction (lelang) -----------------------------
@api.post("/fish-sales")
async def create_fish_sale(body: FishSaleCreate,
                          user: dict = Depends(require_roles("PETUGAS_LAPANG", "ADMIN"))):
    vessel = await vessels.find_one({"vessel_id": body.vessel_id}, {"_id": 0})
    if not vessel:
        raise HTTPException(status_code=404, detail="Perahu tidak ditemukan")
    fish = await fish_prices.find_one({"fish_id": body.fish_id}, {"_id": 0})
    if not fish:
        raise HTTPException(status_code=404, detail="Jenis ikan tidak ditemukan")
    if body.weight_kg <= 0:
        raise HTTPException(status_code=400, detail="Berat harus lebih dari 0")
    if body.payment_method not in ("CASH", "QRIS", "TRANSFER", "POTONG_UTANG"):
        raise HTTPException(status_code=400, detail="Metode pembayaran tidak valid")

    price = float(body.price_per_kg) if body.price_per_kg else float(fish["price_per_kg"])
    gross = round(body.weight_kg * price, 2)
    fisherman_id = vessel["owner_id"]
    amount_deducted = 0.0

    if body.payment_method == "POTONG_UTANG":
        # Apply proceeds to outstanding BBM/modal debt (oldest first)
        remaining = gross
        debts = await transactions.find(
            {"fisherman_id": fisherman_id, "status": "DP", "remaining_balance": {"$gt": 0}},
            {"_id": 0}).sort("created_at", 1).to_list(1000)
        for d in debts:
            if remaining <= 0:
                break
            pay = min(remaining, d["remaining_balance"])
            new_bal = round(d["remaining_balance"] - pay, 2)
            await transactions.update_one(
                {"transaction_id": d["transaction_id"]},
                {"$set": {"remaining_balance": new_bal, "status": "LUNAS" if new_bal <= 0 else "DP"}})
            remaining = round(remaining - pay, 2)
            amount_deducted = round(amount_deducted + pay, 2)
    cash_paid = round(gross - amount_deducted, 2)

    doc = {
        "sale_id": gen_id("sale"), "vessel_id": vessel["vessel_id"], "vessel_name": vessel["vessel_name"],
        "fisherman_id": fisherman_id, "fisherman_name": vessel["owner_name"],
        "fish_id": fish["fish_id"], "fish_name": fish["name"], "weight_kg": body.weight_kg,
        "price_per_kg": price, "gross_amount": gross, "payment_method": body.payment_method,
        "payment_ref": body.payment_ref, "amount_deducted": amount_deducted,
        "cash_paid": cash_paid, "notes": body.notes,
        "recorded_by": user["user_id"], "recorded_by_name": user["name"],
        "is_validated": False, "receipt_photo_url": None, "validated_by": None,
        "created_at": now_utc().isoformat(),
    }
    await fish_sales.insert_one(dict(doc))
    doc.pop("_id", None)

    if body.payment_method == "POTONG_UTANG":
        msg = (f"Lelang {body.weight_kg:.0f}kg {fish['name']} = Rp{gross:,.0f}. "
               f"Dipotong utang Rp{amount_deducted:,.0f}, tunai Rp{cash_paid:,.0f}.")
    else:
        msg = f"Lelang {body.weight_kg:.0f}kg {fish['name']} = Rp{gross:,.0f} dibayar tunai."
    await add_notification(fisherman_id, msg, "INFO")
    return doc


@api.get("/fish-sales")
async def list_fish_sales(user: dict = Depends(get_current_user)):
    if user["role"] in ("ADMIN", "PETUGAS_LAPANG", "PETUGAS_DINAS"):
        q = {}
    else:
        q = {"fisherman_id": user["user_id"]}
    return await fish_sales.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)


@api.post("/fish-sales/{sale_id}/validate")
async def validate_fish_sale(sale_id: str, body: ValidateTransaction,
                            user: dict = Depends(require_roles("ADMIN"))):
    sale = await fish_sales.find_one({"sale_id": sale_id})
    if not sale:
        raise HTTPException(status_code=404, detail="Transaksi lelang tidak ditemukan")
    await fish_sales.update_one({"sale_id": sale_id}, {"$set": {
        "is_validated": True, "receipt_photo_url": body.receipt_photo_url,
        "validated_by": user["name"],
    }})
    await add_notification(sale["fisherman_id"],
                           f"Transaksi lelang {sale['weight_kg']:.0f}kg {sale['fish_name']} telah divalidasi koperasi.",
                           "INFO")
    return {"ok": True}


# ----------------------------- reports -----------------------------
async def report_summary_data(start: str = None, end: str = None):
    start_iso, end_iso = parse_period(start, end)
    date_q = {"created_at": {"$gte": start_iso, "$lte": end_iso}}
    trx = await transactions.find(date_q, {"_id": 0}).to_list(5000)
    sales = await fish_sales.find(date_q, {"_id": 0}).to_list(5000)
    savings = await savings_entries.find(date_q, {"_id": 0}).to_list(5000)
    loan_docs = await loans.find(date_q, {"_id": 0}).to_list(5000)
    payments = await loan_payments.find(date_q, {"_id": 0}).to_list(5000)
    inv = await inventory_movements.find(date_q, {"_id": 0}).to_list(5000)
    debts = await transactions.find({"status": "DP", "remaining_balance": {"$gt": 0}}, {"_id": 0}).to_list(5000)
    cash_in = (
        sum(t.get("amount_paid", 0) for t in trx)
        + sum(s.get("cash_paid", 0) for s in sales)
        + sum(x["amount"] for x in savings if x["direction"] == "DEPOSIT")
        + sum(p["amount"] for p in payments)
    )
    cash_out = sum(x["amount"] for x in savings if x["direction"] == "WITHDRAWAL") + sum(l["amount"] for l in loan_docs if l["status"] in ("APPROVED", "DISBURSED", "PAID"))
    return {
        "period": {"start": start_iso, "end": end_iso},
        "bbm_revenue": round(sum(t.get("amount_paid", 0) for t in trx), 2),
        "fish_sales_gross": round(sum(s.get("gross_amount", 0) for s in sales), 2),
        "savings_in": round(sum(x["amount"] for x in savings if x["direction"] == "DEPOSIT"), 2),
        "savings_out": round(sum(x["amount"] for x in savings if x["direction"] == "WITHDRAWAL"), 2),
        "loan_disbursed": round(sum(l["amount"] for l in loan_docs if l["status"] in ("APPROVED", "DISBURSED", "PAID")), 2),
        "loan_payments": round(sum(p["amount"] for p in payments), 2),
        "inventory_movements": len(inv),
        "active_debt": round(sum(d["remaining_balance"] for d in debts), 2),
        "cash_in": round(cash_in, 2),
        "cash_out": round(cash_out, 2),
        "net_cash": round(cash_in - cash_out, 2),
        "counts": {
            "transactions": len(trx), "fish_sales": len(sales), "savings": len(savings),
            "loans": len(loan_docs), "loan_payments": len(payments), "inventory": len(inv),
        },
    }

@api.get("/reports/summary")
async def reports_summary(start: str = Query(None), end: str = Query(None), user: dict = Depends(require_roles("ADMIN"))):
    return await report_summary_data(start, end)

@api.get("/reports/transactions.csv")
async def reports_transactions_csv(start: str = Query(None), end: str = Query(None), user: dict = Depends(require_roles("ADMIN"))):
    start_iso, end_iso = parse_period(start, end)
    rows = await transactions.find({"created_at": {"$gte": start_iso, "$lte": end_iso}}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return csv_response("syncoop-transaksi.csv", rows, ["created_at", "transaction_id", "fisherman_name", "vessel_name", "liters_bought", "total_price", "amount_paid", "remaining_balance", "status", "payment_method", "payment_ref"])

@api.get("/reports/loans.csv")
async def reports_loans_csv(start: str = Query(None), end: str = Query(None), user: dict = Depends(require_roles("ADMIN"))):
    start_iso, end_iso = parse_period(start, end)
    rows = await loans.find({"created_at": {"$gte": start_iso, "$lte": end_iso}}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return csv_response("syncoop-pinjaman.csv", rows, ["created_at", "loan_id", "member_name", "amount", "purpose", "tenor_months", "status", "outstanding_balance", "approved_by"])

@api.get("/reports/inventory.csv")
async def reports_inventory_csv(start: str = Query(None), end: str = Query(None), user: dict = Depends(require_roles("ADMIN"))):
    start_iso, end_iso = parse_period(start, end)
    rows = await inventory_movements.find({"created_at": {"$gte": start_iso, "$lte": end_iso}}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return csv_response("syncoop-inventori.csv", rows, ["created_at", "movement_id", "item_name", "movement_type", "quantity", "unit", "stock_after", "reason", "reference", "recorded_by_name"])

# ----------------------------- service / announcements -----------------------------
@api.get("/announcements")
async def list_announcements(user: dict = Depends(get_current_user)):
    q = {"audience": {"$in": ["PUBLIC", "MEMBERS"]}}
    if user["role"] in ("ADMIN", "PETUGAS_LAPANG", "PETUGAS_DINAS"):
        q = {}
    return {"items": await announcements.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)}

@api.post("/announcements")
async def create_announcement(body: AnnouncementCreate, user: dict = Depends(require_roles("ADMIN"))):
    if body.audience not in ("PUBLIC", "MEMBERS", "STAFF"):
        raise HTTPException(status_code=400, detail="Audience tidak valid")
    doc = {
        "announcement_id": gen_id("ann"), "title": body.title, "body": body.body,
        "audience": body.audience, "created_by": user["name"], "created_at": now_utc().isoformat(),
    }
    await announcements.insert_one(doc)
    return clean_doc(doc)

@api.get("/tickets")
async def list_tickets(user: dict = Depends(get_current_user)):
    q = {} if user["role"] in ("ADMIN", "PETUGAS_LAPANG") else {"user_id": user["user_id"]}
    items = await service_tickets.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return {"items": items, "count": len(items)}

@api.post("/tickets")
async def create_ticket(body: ServiceTicketCreate, user: dict = Depends(get_current_user)):
    doc = {
        "ticket_id": gen_id("tic"), "user_id": user["user_id"], "contact_name": user["name"],
        "contact_phone": body.contact_phone or user.get("phone"), "category": body.category,
        "subject": body.subject, "message": body.message, "status": "OPEN",
        "is_public": False, "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat(),
    }
    await service_tickets.insert_one(doc)
    return clean_doc(doc)

@api.post("/tickets/{ticket_id}/reply")
async def reply_ticket(ticket_id: str, body: TicketReplyCreate, user: dict = Depends(require_roles("ADMIN", "PETUGAS_LAPANG"))):
    ticket = await service_tickets.find_one({"ticket_id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    doc = {
        "message_id": gen_id("msg"), "ticket_id": ticket_id, "sender_id": user["user_id"],
        "sender_name": user["name"], "message": body.message, "created_at": now_utc().isoformat(),
    }
    await ticket_messages.insert_one(doc)
    await service_tickets.update_one({"ticket_id": ticket_id}, {"$set": {"status": "IN_PROGRESS", "updated_at": now_utc().isoformat()}})
    if ticket.get("user_id"):
        await add_notification(ticket["user_id"], f"Tiket layanan '{ticket['subject']}' telah dibalas.", "INFO")
    return clean_doc(doc)

@api.put("/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, body: TicketStatusUpdate, user: dict = Depends(require_roles("ADMIN", "PETUGAS_LAPANG"))):
    if body.status not in ("OPEN", "IN_PROGRESS", "RESOLVED"):
        raise HTTPException(status_code=400, detail="Status tidak valid")
    res = await service_tickets.update_one({"ticket_id": ticket_id}, {"$set": {"status": body.status, "updated_at": now_utc().isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    return {"ok": True}

# ----------------------------- public portal -----------------------------
@api.get("/public/portal")
async def public_portal():
    fish = await fish_prices.find({}, {"_id": 0}).sort("name", 1).to_list(20)
    anns = await announcements.find({"audience": "PUBLIC"}, {"_id": 0}).sort("created_at", -1).to_list(5)
    trx_docs = await transactions.find({}, {"_id": 0, "total_price": 1, "liters_bought": 1}).to_list(10000)
    sale_docs = await fish_sales.find({}, {"_id": 0, "gross_amount": 1}).to_list(10000)
    transaction_count = await transactions.count_documents({}) + await fish_sales.count_documents({})
    transaction_value = round(
        sum(t.get("total_price", 0) for t in trx_docs)
        + sum(s.get("gross_amount", 0) for s in sale_docs),
        2,
    )
    stats = {
        "members": await users.count_documents({"role": "NELAYAN"}),
        "vessels": await vessels.count_documents({}),
        "transactions": transaction_count,
        "transaction_value": transaction_value,
        "fuel_liters": round(sum(t.get("liters_bought", 0) for t in trx_docs), 2),
        "fish_prices": len(fish),
    }
    return {"stats": stats, "portal": await get_public_portal_settings(), "fish_prices": fish, "announcements": anns}

@api.post("/public/tickets")
async def create_public_ticket(body: ServiceTicketCreate):
    doc = {
        "ticket_id": gen_id("tic"), "user_id": None, "contact_name": body.contact_name or "Warga",
        "contact_phone": body.contact_phone, "category": body.category, "subject": body.subject,
        "message": body.message, "status": "OPEN", "is_public": True,
        "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat(),
    }
    await service_tickets.insert_one(doc)
    return {"ok": True, "ticket_id": doc["ticket_id"]}

# ----------------------------- file upload / serve -----------------------------
MIME_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf",
}


@api.post("/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(require_roles("ADMIN", "PETUGAS_LAPANG"))):
    ext = (file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "bin")
    content_type = file.content_type or MIME_TYPES.get(ext, "application/octet-stream")
    path = f"{objstore.APP_NAME}/uploads/{user['user_id']}/{gen_id('f')}.{ext}"
    data = await file.read()
    try:
        result = objstore.put_object(path, data, content_type)
    except Exception as e:
        logger.error(f"upload failed: {e}")
        raise HTTPException(status_code=502, detail="Gagal mengunggah file")
    await db.files.insert_one({
        "file_id": gen_id("file"), "storage_path": result["path"],
        "provider": result.get("provider"), "url": result.get("url"),
        "resource_type": result.get("resource_type"), "format": result.get("format"),
        "original_filename": file.filename, "content_type": content_type,
        "size": result.get("size", len(data)), "uploaded_by": user["user_id"],
        "is_deleted": False, "created_at": now_utc().isoformat(),
    })
    return {"path": result["path"], "url": result.get("url") or f"/api/files/{result['path']}"}


async def _verify_token(token: str):
    if not token:
        return None
    session = await sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return None
    return session


@api.get("/files/{path:path}")
async def serve_file(path: str, request: Request, auth: str = Query(None)):
    token = request.cookies.get("session_token")
    if not token:
        ah = request.headers.get("Authorization", "")
        token = ah[7:] if ah.startswith("Bearer ") else None
    token = token or auth
    if not await _verify_token(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    record = await db.files.find_one({"storage_path": path, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    if record.get("url"):
        return RedirectResponse(record["url"], status_code=302)
    try:
        data, ctype = objstore.get_object(path)
    except Exception:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    return Response(content=data, media_type=record.get("content_type", ctype))


# ----------------------------- notifications -----------------------------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    docs = await notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    unread = sum(1 for d in docs if not d["is_read"])
    return {"items": docs, "unread": unread}


@api.post("/notifications/{notif_id}/read")
async def read_notification(notif_id: str, user: dict = Depends(get_current_user)):
    await notifications.update_one({"notif_id": notif_id, "user_id": user["user_id"]},
                                   {"$set": {"is_read": True}})
    return {"ok": True}


# ----------------------------- admin users -----------------------------
@api.get("/admin/users")
async def admin_list_users(user: dict = Depends(require_roles("ADMIN"))):
    return await users.find({}, {
        "_id": 0,
        "pin_hash": 0,
        "biometric_credential_id": 0,
        "biometric_enabled": 0,
        "biometric_device_name": 0,
        "biometric_registered_at": 0,
    }).sort("created_at", -1).to_list(1000)


@api.put("/admin/users/{user_id}/role")
async def admin_set_role(user_id: str, body: RoleUpdate, user: dict = Depends(require_roles("ADMIN"))):
    if body.role not in ("NELAYAN", "PETUGAS_LAPANG", "ADMIN", "PETUGAS_DINAS"):
        raise HTTPException(status_code=400, detail="Peran tidak valid")
    await users.update_one({"user_id": user_id}, {"$set": {"role": body.role}})
    return {"ok": True}


@api.post("/admin/kyc/{user_id}/approve")
async def admin_approve_kyc(user_id: str, user: dict = Depends(require_roles("ADMIN"))):
    await users.update_one({"user_id": user_id},
                           {"$set": {"is_kyc_approved": True, "kyc_status": "APPROVED"}})
    await add_notification(user_id, "Selamat! KYC Anda disetujui. Status: Anggota Penuh.", "INFO")
    return {"ok": True}


# ----------------------------- dashboard stats -----------------------------
@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    role = user["role"]
    mk = month_key()
    stats = {"role": role}
    if role == "NELAYAN":
        my_vessels = await vessels.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(100)
        total_quota = sum(v["monthly_quota_max"] for v in my_vessels)
        used = 0.0
        for v in my_vessels:
            used += await _vessel_used(v["vessel_id"])
        debts = await transactions.find({"fisherman_id": user["user_id"], "status": "DP", "remaining_balance": {"$gt": 0}}, {"_id": 0}).to_list(1000)
        stats.update({
            "vessel_count": len(my_vessels),
            "quota_total": total_quota, "quota_used": round(used, 2),
            "quota_remaining": max(0, round(total_quota - used, 2)),
            "outstanding_debt": round(sum(d["remaining_balance"] for d in debts), 2),
            "debt_count": len(debts),
        })
    elif role == "PETUGAS_DINAS":
        stats.update({
            "total_vessels": await vessels.count_documents({}),
            "pas_besar": await vessels.count_documents({"vessel_type": "PAS_BESAR"}),
            "pas_kecil": await vessels.count_documents({"vessel_type": "PAS_KECIL"}),
            "total_fishermen": await users.count_documents({"role": "NELAYAN"}),
        })
    elif role == "PETUGAS_LAPANG":
        today_count = await transactions.count_documents({"month_key": mk})
        liters_docs = await transactions.find({"month_key": mk}, {"_id": 0, "liters_bought": 1}).to_list(5000)
        stats.update({
            "transactions_this_month": today_count,
            "liters_this_month": round(sum(d["liters_bought"] for d in liters_docs), 2),
            "pending_validation": await transactions.count_documents({"is_validated": False}),
        })
    else:  # ADMIN
        debts = await transactions.find({"status": "DP", "remaining_balance": {"$gt": 0}}, {"_id": 0}).to_list(5000)
        stats.update({
            "total_users": await users.count_documents({}),
            "total_vessels": await vessels.count_documents({}),
            "total_transactions": await transactions.count_documents({}),
            "pending_validation": await transactions.count_documents({"is_validated": False}),
            "pending_sale_validation": await fish_sales.count_documents({"is_validated": False}),
            "total_outstanding": round(sum(d["remaining_balance"] for d in debts), 2),
            "debtor_count": len(debts),
            "pending_kyc": await users.count_documents({"kyc_status": "PENDING"}),
            "portal": await get_public_portal_settings(),
        })
    return stats


# ----------------------------- seed -----------------------------
async def seed():
    if not await settings.find_one({"key": "profit_sharing_percent"}):
        await settings.insert_one({"key": "profit_sharing_percent", "value": DEFAULT_PROFIT_SHARING})
    if not await settings.find_one({"key": "bbm_price_per_liter"}):
        await settings.insert_one({"key": "bbm_price_per_liter", "value": DEFAULT_BBM_PRICE})
    if not await settings.find_one({"key": "public_portal"}):
        await settings.insert_one({"key": "public_portal", "value": DEFAULT_PUBLIC_PORTAL})

    if await fish_prices.count_documents({}) == 0:
        defaults = [
            ("Ikan Tongkol", 28000), ("Ikan Kembung", 32000), ("Ikan Tenggiri", 55000),
            ("Cumi-cumi", 60000), ("Udang", 85000), ("Ikan Kakap", 70000),
        ]
        for n, p in defaults:
            await fish_prices.insert_one({"fish_id": gen_id("fsh"), "name": n, "price_per_kg": float(p)})

    if await inventory_items.count_documents({}) == 0:
        defaults = [
            ("Solar Subsidi", "BBM", "liter", 500),
            ("Es Balok", "Operasional", "balok", 20),
            ("Jaring Pukat", "Alat Tangkap", "unit", 3),
            ("Beras Koperasi", "Sembako", "kg", 50),
        ]
        for n, c, u, m in defaults:
            await inventory_items.insert_one({
                "item_id": gen_id("itm"), "name": n, "category": c, "unit": u,
                "stock": m * 2, "min_stock": float(m), "created_by": "Seed",
                "created_at": now_utc().isoformat(),
            })

    if await announcements.count_documents({}) == 0:
        await announcements.insert_many([
            {
                "announcement_id": gen_id("ann"), "title": "Harga ikan diperbarui setiap pagi",
                "body": "Pantau harga acuan harian sebelum lelang dan penjualan ke koperasi.",
                "audience": "PUBLIC", "created_by": "SynCoop", "created_at": now_utc().isoformat(),
            },
            {
                "announcement_id": gen_id("ann"), "title": "Layanan koperasi terbuka untuk warga sekitar",
                "body": "Ajukan pertanyaan, keluhan, atau permintaan pendaftaran melalui portal layanan.",
                "audience": "PUBLIC", "created_by": "SynCoop", "created_at": now_utc().isoformat(),
            },
        ])

    demos = [
        ("nelayan@demo.syncoop.id", "Budi Santoso (Nelayan)", "NELAYAN"),
        ("lapang@demo.syncoop.id", "Andi Petugas Lapang", "PETUGAS_LAPANG"),
        ("admin@demo.syncoop.id", "Sri Admin Koperasi", "ADMIN"),
        ("dinas@demo.syncoop.id", "Dewi Petugas Dinas", "PETUGAS_DINAS"),
    ]
    for email, name, role in demos:
        if not await users.find_one({"email": email}):
            await users.insert_one(await new_user_doc(email, name, role=role))

    nelayan = await users.find_one({"email": "nelayan@demo.syncoop.id"}, {"_id": 0})
    dinas = await users.find_one({"email": "dinas@demo.syncoop.id"}, {"_id": 0})
    lapang = await users.find_one({"email": "lapang@demo.syncoop.id"}, {"_id": 0})

    if nelayan and await vessels.count_documents({"owner_id": nelayan["user_id"]}) == 0:
        v1 = {
            "vessel_id": gen_id("vsl"), "owner_id": nelayan["user_id"], "owner_name": nelayan["name"],
            "owner_email": nelayan["email"], "vessel_name": "KM Bahari Jaya", "vessel_type": "PAS_BESAR",
            "rekom_number": "REK/2026/001", "monthly_quota_max": 400.0,
            "created_by": dinas["name"] if dinas else "Dinas", "created_at": now_utc().isoformat(),
        }
        v2 = {
            "vessel_id": gen_id("vsl"), "owner_id": nelayan["user_id"], "owner_name": nelayan["name"],
            "owner_email": nelayan["email"], "vessel_name": "Perahu Samudra", "vessel_type": "PAS_KECIL",
            "rekom_number": "REK/2026/002", "monthly_quota_max": 400.0,
            "created_by": dinas["name"] if dinas else "Dinas", "created_at": now_utc().isoformat(),
        }
        await vessels.insert_many([v1, v2])
        price = DEFAULT_BBM_PRICE
        trx = {
            "transaction_id": gen_id("trx"), "vessel_id": v1["vessel_id"], "vessel_name": v1["vessel_name"],
            "fisherman_id": nelayan["user_id"], "fisherman_name": nelayan["name"], "liters_bought": 150.0,
            "price_per_liter": price, "total_price": 150 * price, "amount_paid": 500000.0, "status": "DP",
            "remaining_balance": 150 * price - 500000.0, "receipt_photo_url": None, "is_validated": False,
            "recorded_by": lapang["user_id"] if lapang else "x", "recorded_by_name": lapang["name"] if lapang else "Lapang",
            "validated_by": None, "debt_reason": None, "month_key": month_key(), "created_at": now_utc().isoformat(),
        }
        await transactions.insert_one(trx)
        await add_notification(nelayan["user_id"],
                               f"Transaksi 150L tercatat dengan kurang bayar Rp{trx['remaining_balance']:,.0f}. Mohon isi alasan penundaan.",
                               "DEBT", trx["transaction_id"])

    if nelayan and await savings_entries.count_documents({"member_id": nelayan["user_id"]}) == 0:
        await savings_entries.insert_many([
            {
                "entry_id": gen_id("sav"), "member_id": nelayan["user_id"], "member_name": nelayan["name"],
                "member_email": nelayan["email"], "entry_type": "POKOK", "direction": "DEPOSIT",
                "amount": 250000.0, "notes": "Setoran awal anggota", "recorded_by": "seed",
                "recorded_by_name": "SynCoop", "created_at": now_utc().isoformat(),
            },
            {
                "entry_id": gen_id("sav"), "member_id": nelayan["user_id"], "member_name": nelayan["name"],
                "member_email": nelayan["email"], "entry_type": "WAJIB", "direction": "DEPOSIT",
                "amount": 50000.0, "notes": "Simpanan wajib bulan berjalan", "recorded_by": "seed",
                "recorded_by_name": "SynCoop", "created_at": now_utc().isoformat(),
            },
        ])

    if nelayan and await loans.count_documents({"member_id": nelayan["user_id"]}) == 0:
        await loans.insert_one({
            "loan_id": gen_id("loan"), "member_id": nelayan["user_id"], "member_name": nelayan["name"],
            "member_email": nelayan["email"], "amount": 1500000.0, "purpose": "Perbaikan mesin perahu",
            "tenor_months": 6, "status": "APPROVED", "outstanding_balance": 1000000.0,
            "approved_by": "Sri Admin Koperasi", "approved_at": now_utc().isoformat(),
            "decision_notes": "Riwayat transaksi baik", "created_at": now_utc().isoformat(),
        })


@app.on_event("startup")
async def on_startup():
    try:
        objstore.init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.warning(f"Storage disabled: {e}")
    try:
        await seed()
        await disable_legacy_biometric_flags()
        logger.info("Seed complete")
    except Exception as e:
        logger.error(f"Seed error: {e}")


@api.get("/")
async def root():
    return {"message": "SynCoop API", "status": "ok"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ] + CORS_ORIGINS,
    allow_origin_regex=r"https://([a-z0-9-]+\.)?syncoop\.pages\.dev|https://.*\.(preview\.emergentagent\.com|emergentagent\.com|emergent\.host)",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    db.client.close()

