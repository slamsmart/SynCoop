import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, CheckCircle2, AlertTriangle, X, Camera } from "lucide-react";
import api, { fmtRp } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Badge, Empty } from "@/components/ui-kit";

export default function Transactions() {
  const { user } = useAuth();
  const [trx, setTrx] = useState([]);
  const [sales, setSales] = useState([]);
  const [vessels, setVessels] = useState([]);
  const [tab, setTab] = useState("bbm");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ vessel_id: "", liters_bought: "", amount_paid: "" });
  const [quotaAlert, setQuotaAlert] = useState(null);
  const [validateFor, setValidateFor] = useState(null);
  const [photoUrl, setPhotoUrl] = useState("");

  const isLapang = user.role === "PETUGAS_LAPANG" || user.role === "ADMIN";
  const isAdmin = user.role === "ADMIN";

  const load = useCallback(() => {
    api.get("/transactions").then((r) => setTrx(r.data)).catch(() => {});
    api.get("/vessels").then((r) => setVessels(r.data)).catch(() => {});
    api.get("/fish-sales").then((r) => setSales(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const submit = async () => {
    setQuotaAlert(null);
    try {
      await api.post("/transactions", {
        vessel_id: form.vessel_id,
        liters_bought: parseFloat(form.liters_bought),
        amount_paid: parseFloat(form.amount_paid || 0),
      });
      setShowForm(false);
      setForm({ vessel_id: "", liters_bought: "", amount_paid: "" });
      load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (d && typeof d === "object" && d.code === "QUOTA_EXCEEDED") setQuotaAlert(d);
      else alert(typeof d === "string" ? d : "Gagal mencatat transaksi");
    }
  };

  const doValidate = async () => {
    try {
      const url = validateFor.sale_id
        ? `/fish-sales/${validateFor.sale_id}/validate`
        : `/transactions/${validateFor.transaction_id}/validate`;
      await api.post(url, { receipt_photo_url: photoUrl });
      setValidateFor(null); setPhotoUrl(""); load();
    } catch { alert("Gagal validasi"); }
  };

  const selectedVessel = vessels.find((v) => v.vessel_id === form.vessel_id);

  return (
    <div data-testid="transactions-page">
      <PageHeader
        kicker={isAdmin ? "Verifikasi Buku Besar" : "Pencatatan Dockside"}
        title={isAdmin ? "Validasi Transaksi" : "Catat Transaksi BBM"}
        desc={isAdmin ? "Validasi entri lapangan & unggah bukti fisik nota." : "Catat pembelian BBM nelayan di dermaga."}
        action={isLapang && tab === "bbm" ? (
          <button data-testid="add-trx-btn" onClick={() => setShowForm(!showForm)} className="tap btn-primary px-5 font-semibold flex items-center gap-2">
            <Plus size={18} /> Transaksi Baru
          </button>
        ) : null}
      />

      {isAdmin && (
        <div className="flex gap-px bg-[var(--line)] border hairline mb-8 w-full sm:w-auto sm:inline-flex">
          <button data-testid="tab-bbm" onClick={() => setTab("bbm")}
            className={`px-6 h-12 text-sm font-semibold transition-colors ${tab === "bbm" ? "bg-[var(--ink)] text-white" : "bg-white"}`}>
            Transaksi BBM {trx.filter((t) => !t.is_validated).length > 0 && `(${trx.filter((t) => !t.is_validated).length})`}
          </button>
          <button data-testid="tab-lelang" onClick={() => setTab("lelang")}
            className={`px-6 h-12 text-sm font-semibold transition-colors ${tab === "lelang" ? "bg-[var(--ink)] text-white" : "bg-white"}`}>
            Lelang Ikan {sales.filter((s) => !s.is_validated).length > 0 && `(${sales.filter((s) => !s.is_validated).length})`}
          </button>
        </div>
      )}

      {tab === "lelang" && isAdmin ? (
        sales.length === 0 ? <Empty>Belum ada transaksi lelang.</Empty> : (
          <div className="border hairline divide-y divide-[var(--line)]">
            {sales.map((s) => (
              <div key={s.sale_id} data-testid="sale-validate-row" className="p-5 flex flex-col sm:flex-row sm:items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold">{s.fish_name} · {s.weight_kg} kg</span>
                    <Badge tone={s.payment_method === "CASH" ? "ok" : "ink"}>{s.payment_method === "CASH" ? "Tunai" : "Potong Utang"}</Badge>
                    {s.is_validated ? <Badge tone="ink">Tervalidasi</Badge> : <Badge tone="outline">Belum Validasi</Badge>}
                  </div>
                  <p className="text-sm text-[var(--muted)] mt-1">{s.fisherman_name} · {fmtRp(s.gross_amount)} · oleh {s.recorded_by_name}</p>
                </div>
                <div className="text-right">
                  {!s.is_validated && (
                    <button data-testid="validate-sale-btn" onClick={() => setValidateFor(s)}
                      className="btn-outline px-3 py-1.5 text-sm font-semibold flex items-center gap-1 ml-auto">
                      <CheckCircle2 size={14} /> Validasi Nota
                    </button>
                  )}
                  {s.receipt_photo_url && <a href={s.receipt_photo_url} target="_blank" rel="noreferrer" className="mono-label block mt-1">lihat bukti</a>}
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
      <>
      {showForm && (
        <div data-testid="trx-form" className="border hairline p-6 mb-8 grid grid-cols-1 md:grid-cols-3 gap-4 fade-up">
          <div className="md:col-span-3">
            <label className="mono-label">Perahu Nelayan</label>
            <select data-testid="trx-vessel" className="field tap w-full px-4 mt-2"
              value={form.vessel_id} onChange={(e) => setForm({ ...form, vessel_id: e.target.value })}>
              <option value="">— Pilih perahu —</option>
              {vessels.map((v) => (
                <option key={v.vessel_id} value={v.vessel_id}>
                  {v.vessel_name} · {v.owner_name} · sisa {v.remaining_quota}L
                </option>
              ))}
            </select>
            {selectedVessel && (
              <p className="text-sm text-[var(--muted)] mt-2">Sisa kuota: <b className="text-[var(--ink)]">{selectedVessel.remaining_quota} L</b></p>
            )}
          </div>
          <div>
            <label className="mono-label">Volume (Liter)</label>
            <input data-testid="trx-liters" type="number" className="field tap w-full px-4 mt-2"
              value={form.liters_bought} onChange={(e) => setForm({ ...form, liters_bought: e.target.value })} />
          </div>
          <div>
            <label className="mono-label">Nominal Dibayar (Rp)</label>
            <input data-testid="trx-paid" type="number" className="field tap w-full px-4 mt-2" placeholder="0 = belum bayar"
              value={form.amount_paid} onChange={(e) => setForm({ ...form, amount_paid: e.target.value })} />
          </div>
          <div className="flex items-end">
            <button data-testid="trx-submit" onClick={submit} disabled={!form.vessel_id || !form.liters_bought}
              className="tap btn-primary w-full font-semibold disabled:opacity-40">Catat</button>
          </div>
        </div>
      )}

      {trx.length === 0 ? <Empty>Belum ada transaksi.</Empty> : (
        <div className="border hairline divide-y divide-[var(--line)]">
          {trx.map((t) => (
            <div key={t.transaction_id} data-testid="trx-row" className="p-5 flex flex-col sm:flex-row sm:items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold">{t.vessel_name}</span>
                  <Badge tone={t.status === "LUNAS" ? "ok" : "danger"}>{t.status}</Badge>
                  {t.is_validated ? <Badge tone="ink">Tervalidasi</Badge> : <Badge tone="outline">Belum Validasi</Badge>}
                </div>
                <p className="text-sm text-[var(--muted)] mt-1">
                  {t.fisherman_name} · {t.liters_bought} L · {fmtRp(t.total_price)} · oleh {t.recorded_by_name}
                </p>
                {t.debt_reason && <p className="text-sm mt-1 lav inline-block px-2 py-1">Alasan: {t.debt_reason}</p>}
              </div>
              <div className="text-right">
                {t.remaining_balance > 0 ? (
                  <p className="font-semibold text-[var(--danger)]">Kurang {fmtRp(t.remaining_balance)}</p>
                ) : <p className="font-semibold text-[var(--ok)]">Lunas</p>}
                {isAdmin && !t.is_validated && (
                  <button data-testid="validate-btn" onClick={() => setValidateFor(t)}
                    className="mt-2 btn-outline px-3 py-1.5 text-sm font-semibold flex items-center gap-1 ml-auto">
                    <CheckCircle2 size={14} /> Validasi
                  </button>
                )}
                {t.receipt_photo_url && <a href={t.receipt_photo_url} target="_blank" rel="noreferrer" className="mono-label block mt-1">lihat bukti</a>}
              </div>
            </div>
          ))}
        </div>
      )}
      </>
      )}

      {/* Quota exceeded alert */}
      <AnimatePresence>
        {quotaAlert && (
          <Overlay onClose={() => setQuotaAlert(null)}>
            <div data-testid="quota-alert" className="text-center">
              <div className="w-14 h-14 bg-[var(--danger)] text-white flex items-center justify-center mx-auto">
                <AlertTriangle size={26} />
              </div>
              <h3 className="swiss-display text-2xl mt-5">Kuota Habis</h3>
              <p className="text-[var(--muted)] mt-2">{quotaAlert.message}</p>
              <div className="mt-6 h-3 bg-[var(--lavender)]">
                <div className="h-3 bg-[var(--danger)]" style={{ width: `${Math.min(100, (quotaAlert.used / quotaAlert.max) * 100)}%` }} />
              </div>
              <div className="flex justify-between mono-label mt-2">
                <span>Terpakai {quotaAlert.used} L</span><span>Maks {quotaAlert.max} L</span>
              </div>
              <button onClick={() => setQuotaAlert(null)} className="tap btn-primary w-full mt-6 font-semibold">Mengerti</button>
            </div>
          </Overlay>
        )}
      </AnimatePresence>

      {/* Validate modal */}
      <AnimatePresence>
        {validateFor && (
          <Overlay onClose={() => setValidateFor(null)}>
            <h3 className="swiss-display text-2xl">Unggah Bukti Fisik</h3>
            <p className="text-[var(--muted)] mt-2 text-sm">Foto/scan coretan kwitansi atau nota petugas lapang untuk {validateFor.sale_id ? `lelang ${validateFor.fish_name}` : `BBM ${validateFor.vessel_name}`}.</p>
            <div className="flex items-center gap-2 mt-5">
              <Camera size={18} />
              <input data-testid="receipt-url" className="field tap flex-1 px-4" placeholder="https://… url foto bukti"
                value={photoUrl} onChange={(e) => setPhotoUrl(e.target.value)} />
            </div>
            <button onClick={() => setPhotoUrl("https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=600")}
              className="mono-label mt-3">gunakan contoh foto</button>
            <button data-testid="validate-confirm" onClick={doValidate} disabled={!photoUrl}
              className="tap btn-primary w-full mt-6 font-semibold disabled:opacity-40">Validasi & Masukkan ke Buku Besar</button>
          </Overlay>
        )}
      </AnimatePresence>
    </div>
  );
}

function Overlay({ children, onClose }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <motion.div initial={{ scale: 0.95, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()} className="bg-white border hairline p-8 w-full max-w-md relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-[var(--muted)]"><X size={20} /></button>
        {children}
      </motion.div>
    </motion.div>
  );
}
