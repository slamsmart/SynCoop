import os
import logging
from datetime import datetime, timezone, timedelta

import requests
from fastapi import (
    FastAPI, APIRouter, HTTPException, Request, Response, Depends,
    UploadFile, File, Header, Query,
)
from starlette.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

from database import (
    db, users, sessions, vessels, transactions, fish_prices, fish_calcs,
    fish_sales, notifications, settings,
)
import storage as objstore
from models import (
    User, PinSet, PinLogin, DemoLogin, KycSubmit, VesselCreate, Vessel,
    Transaction, TransactionCreate, ValidateTransaction, DebtReason, FishPriceCreate,
    FishCalcRequest, ProfitSharing, RoleUpdate, FishSaleCreate, now_utc, gen_id,
)
from deps import get_current_user, require_roles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("syncoop")

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
MATURATION_DAYS = 365
DEFAULT_BBM_PRICE = 6800.0
DEFAULT_PROFIT_SHARING = 10.0

app = FastAPI()
api = APIRouter(prefix="/api")


# ----------------------------- helpers -----------------------------
def public_user(u: dict) -> dict:
    u.pop("pin_hash", None)
    u.pop("_id", None)
    return u


def month_key(dt: datetime = None) -> str:
    dt = dt or now_utc()
    return dt.strftime("%Y-%m")


async def get_setting(key: str, default):
    doc = await settings.find_one({"key": key}, {"_id": 0})
    return doc["value"] if doc else default


async def create_session(user_id: str) -> str:
    token = gen_id("sess") + gen_id("t")
    expires = now_utc() + timedelta(days=7)
    await sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": expires.isoformat(),
        "created_at": now_utc().isoformat(),
    })
    return token


def set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session_token", value=token, httponly=True, secure=True,
        samesite="none", path="/", max_age=7 * 24 * 60 * 60,
    )


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
        "has_pin": False,
        "phone": None, "nik": None, "address": None,
    }


async def add_notification(user_id: str, message: str, ntype: str = "INFO", related=None):
    await notifications.insert_one({
        "notif_id": gen_id("ntf"), "user_id": user_id, "message": message,
        "type": ntype, "related_transaction_id": related, "is_read": False,
        "created_at": now_utc().isoformat(),
    })


# ----------------------------- auth -----------------------------
@api.post("/auth/session")
async def auth_session(request: Request, response: Response):
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-ID")
    try:
        r = requests.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": session_id}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"oauth error: {e}")
        raise HTTPException(status_code=401, detail="Gagal memverifikasi sesi Google")

    email = data["email"]
    user = await users.find_one({"email": email}, {"_id": 0})
    if not user:
        user = await new_user_doc(email, data.get("name", email), data.get("picture"))
        await users.insert_one(dict(user))
    token = await create_session(user["user_id"])
    set_session_cookie(response, token)
    return public_user(user)


@api.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return user


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


@api.post("/auth/pin/set")
async def set_pin(body: PinSet, user: dict = Depends(get_current_user)):
    if not (body.pin.isdigit() and len(body.pin) == 6):
        raise HTTPException(status_code=400, detail="PIN harus 6 angka")
    await users.update_one({"user_id": user["user_id"]},
                           {"$set": {"pin_hash": pwd.hash(body.pin), "has_pin": True}})
    return {"ok": True}


@api.post("/auth/pin/login")
async def pin_login(body: PinLogin, response: Response):
    user = await users.find_one({"email": body.email})
    if not user or not user.get("pin_hash") or not pwd.verify(body.pin, user["pin_hash"]):
        raise HTTPException(status_code=401, detail="Email atau PIN salah")
    token = await create_session(user["user_id"])
    set_session_cookie(response, token)
    return public_user(user)


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
    token = await create_session(user["user_id"])
    set_session_cookie(response, token)
    return public_user(user)


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
    if body.payment_method not in ("CASH", "POTONG_UTANG"):
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
        "amount_deducted": amount_deducted, "cash_paid": cash_paid, "notes": body.notes,
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
        "original_filename": file.filename, "content_type": content_type,
        "size": result.get("size", len(data)), "uploaded_by": user["user_id"],
        "is_deleted": False, "created_at": now_utc().isoformat(),
    })
    return {"path": result["path"], "url": f"/api/files/{result['path']}"}


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
    return await users.find({}, {"_id": 0, "pin_hash": 0}).sort("created_at", -1).to_list(1000)


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
        })
    return stats


# ----------------------------- seed -----------------------------
async def seed():
    if not await settings.find_one({"key": "profit_sharing_percent"}):
        await settings.insert_one({"key": "profit_sharing_percent", "value": DEFAULT_PROFIT_SHARING})
    if not await settings.find_one({"key": "bbm_price_per_liter"}):
        await settings.insert_one({"key": "bbm_price_per_liter", "value": DEFAULT_BBM_PRICE})

    if await fish_prices.count_documents({}) == 0:
        defaults = [
            ("Ikan Tongkol", 28000), ("Ikan Kembung", 32000), ("Ikan Tenggiri", 55000),
            ("Cumi-cumi", 60000), ("Udang", 85000), ("Ikan Kakap", 70000),
        ]
        for n, p in defaults:
            await fish_prices.insert_one({"fish_id": gen_id("fsh"), "name": n, "price_per_kg": float(p)})

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


@app.on_event("startup")
async def on_startup():
    try:
        objstore.init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    try:
        await seed()
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
    allow_origin_regex=r"https://.*\.(preview\.emergentagent\.com|emergentagent\.com|emergent\.host)",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    db.client.close()
