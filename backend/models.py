import uuid
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------- Auth / User ----------
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "NELAYAN"  # NELAYAN, PETUGAS_LAPANG, ADMIN, PETUGAS_DINAS
    created_at: str
    maturation_end_date: str
    is_kyc_approved: bool = False
    kyc_status: str = "NONE"  # NONE, PENDING, APPROVED
    has_pin: bool = False
    phone: Optional[str] = None
    nik: Optional[str] = None
    address: Optional[str] = None


class PinSet(BaseModel):
    pin: str


class PinLogin(BaseModel):
    email: str
    pin: str


class DemoLogin(BaseModel):
    role: str


class BiometricRegister(BaseModel):
    credential_id: str
    device_name: Optional[str] = None

# ---------- KYC ----------
class KycSubmit(BaseModel):
    nik: str
    phone: str
    address: str


# ---------- Vessel ----------
class VesselCreate(BaseModel):
    owner_email: str
    vessel_name: str
    vessel_type: str  # PAS_BESAR / PAS_KECIL
    rekom_number: str


class Vessel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    vessel_id: str
    owner_id: str
    owner_name: str
    owner_email: str
    vessel_name: str
    vessel_type: str
    rekom_number: str
    monthly_quota_max: float = 400.0
    created_by: str
    created_at: str


# ---------- Transaction ----------
class TransactionCreate(BaseModel):
    vessel_id: str
    liters_bought: float
    amount_paid: float
    payment_method: str = "CASH"  # CASH / QRIS / TRANSFER / PIUTANG
    payment_ref: Optional[str] = None


class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transaction_id: str
    vessel_id: str
    vessel_name: str
    fisherman_id: str
    fisherman_name: str
    liters_bought: float
    price_per_liter: float
    total_price: float
    amount_paid: float
    status: str  # LUNAS / DP
    remaining_balance: float
    receipt_photo_url: Optional[str] = None
    is_validated: bool = False
    recorded_by: str
    recorded_by_name: str
    validated_by: Optional[str] = None
    debt_reason: Optional[str] = None
    month_key: str
    created_at: str


class ValidateTransaction(BaseModel):
    receipt_photo_url: str


class DebtReason(BaseModel):
    reason: str


# ---------- Fish ----------
class FishPriceCreate(BaseModel):
    name: str
    price_per_kg: float


class FishPrice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fish_id: str
    name: str
    price_per_kg: float


class FishCalcRequest(BaseModel):
    fish_id: str
    weight_kg: float


class ProfitSharing(BaseModel):
    profit_sharing_percent: float


# ---------- Fish Sale / Auction (Lelang Ikan) ----------
class PublicPortalSettings(BaseModel):
    hero_kicker: str = "Ekosistem Manajemen Koperasi Nelayan"
    hero_heading: str = "Koperasi nelayan yang transparan dan dekat."
    hero_description: str = "Kelola BBM subsidi & kas koperasi secara transparan. Distribusi BBM tepat sasaran, kalkulator hasil tangkapan, dan pembukuan utang yang adil untuk nelayan akar rumput."
    stat_cards: Optional[List[dict]] = None

class FishSaleCreate(BaseModel):
    vessel_id: str
    fish_id: str
    weight_kg: float
    price_per_kg: Optional[float] = None  # auction override; defaults to market price
    payment_method: str  # CASH / QRIS / TRANSFER / POTONG_UTANG
    payment_ref: Optional[str] = None
    notes: Optional[str] = None

# ---------- Savings / Loans ----------
class SavingsEntryCreate(BaseModel):
    member_email: str
    entry_type: str  # POKOK / WAJIB / SUKARELA
    direction: str = "DEPOSIT"  # DEPOSIT / WITHDRAWAL
    amount: float
    notes: Optional[str] = None

class LoanCreate(BaseModel):
    amount: float
    purpose: str
    tenor_months: int = 6
    member_email: Optional[str] = None

class LoanDecision(BaseModel):
    notes: Optional[str] = None

class LoanPaymentCreate(BaseModel):
    amount: float
    payment_method: str = "CASH"
    payment_ref: Optional[str] = None
    notes: Optional[str] = None

# ---------- Inventory ----------
class InventoryItemCreate(BaseModel):
    name: str
    category: str
    unit: str
    min_stock: float = 0

class InventoryMovementCreate(BaseModel):
    item_id: str
    movement_type: str  # IN / OUT
    quantity: float
    reason: str
    reference: Optional[str] = None

# ---------- Service / Announcements ----------
class ServiceTicketCreate(BaseModel):
    category: str
    subject: str
    message: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None

class TicketReplyCreate(BaseModel):
    message: str

class TicketStatusUpdate(BaseModel):
    status: str  # OPEN / IN_PROGRESS / RESOLVED

class AnnouncementCreate(BaseModel):
    title: str
    body: str
    audience: str = "PUBLIC"  # PUBLIC / MEMBERS / STAFF


# ---------- Admin ----------
class RoleUpdate(BaseModel):
    role: str
