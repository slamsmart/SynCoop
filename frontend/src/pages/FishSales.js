import { useEffect, useState, useCallback } from "react";
import { Plus, Banknote, Scissors, Fish } from "lucide-react";
import api, { fmtRp } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Badge, Empty } from "@/components/ui-kit";

export default function FishSales() {
  const { user } = useAuth();
  const isStaff = user.role === "PETUGAS_LAPANG" || user.role === "ADMIN";
  const [sales, setSales] = useState([]);
  const [vessels, setVessels] = useState([]);
  const [fish, setFish] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ vessel_id: "", fish_id: "", weight_kg: "", price_per_kg: "", payment_method: "CASH", notes: "" });
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    api.get("/fish-sales").then((r) => setSales(r.data)).catch(() => {});
    if (isStaff) {
      api.get("/vessels").then((r) => setVessels(r.data)).catch(() => {});
      api.get("/fish-prices").then((r) => setFish(r.data)).catch(() => {});
    }
  }, [isStaff]);
  useEffect(() => { load(); }, [load]);

  const selVessel = vessels.find((v) => v.vessel_id === form.vessel_id);
  const selFish = fish.find((f) => f.fish_id === form.fish_id);
  const effPrice = parseFloat(form.price_per_kg) || selFish?.price_per_kg || 0;
  const gross = (parseFloat(form.weight_kg) || 0) * effPrice;

  const submit = async () => {
    setErr("");
    try {
      await api.post("/fish-sales", {
        vessel_id: form.vessel_id,
        fish_id: form.fish_id,
        weight_kg: parseFloat(form.weight_kg),
        price_per_kg: form.price_per_kg ? parseFloat(form.price_per_kg) : null,
        payment_method: form.payment_method,
        notes: form.notes || null,
      });
      setShowForm(false);
      setForm({ vessel_id: "", fish_id: "", weight_kg: "", price_per_kg: "", payment_method: "CASH", notes: "" });
      load();
    } catch (e) {
      setErr(e?.response?.data?.detail || "Gagal mencatat lelang");
    }
  };

  return (
    <div data-testid="fish-sales-page">
      <PageHeader
        kicker="Sektor Riil · Tata Niaga Ikan"
        title="Lelang Ikan"
        desc={isStaff ? "Catat pembelian hasil tangkapan nelayan. Bayar tunai atau potong utang modal (tebasan/ijon)." : "Riwayat penjualan hasil tangkapan Anda ke koperasi."}
        action={isStaff ? (
          <button data-testid="add-sale-btn" onClick={() => setShowForm(!showForm)} className="tap btn-primary px-5 font-semibold flex items-center gap-2">
            <Plus size={18} /> Catat Lelang
          </button>
        ) : null}
      />

      {showForm && isStaff && (
        <div data-testid="sale-form" className="border hairline p-6 mb-8 fade-up">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="mono-label">Nelayan (via Perahu)</label>
              <select data-testid="sale-vessel" className="field tap w-full px-4 mt-2"
                value={form.vessel_id} onChange={(e) => setForm({ ...form, vessel_id: e.target.value })}>
                <option value="">— Pilih perahu/nelayan —</option>
                {vessels.map((v) => <option key={v.vessel_id} value={v.vessel_id}>{v.owner_name} · {v.vessel_name}</option>)}
              </select>
              {selVessel && <p className="text-sm text-[var(--muted)] mt-2">Utang modal aktif: <b className="text-[var(--danger)]">{fmtRp(selVessel.owner_outstanding)}</b></p>}
            </div>
            <div>
              <label className="mono-label">Jenis Ikan</label>
              <select data-testid="sale-fish" className="field tap w-full px-4 mt-2"
                value={form.fish_id} onChange={(e) => setForm({ ...form, fish_id: e.target.value })}>
                <option value="">— Pilih jenis ikan —</option>
                {fish.map((f) => <option key={f.fish_id} value={f.fish_id}>{f.name} — {fmtRp(f.price_per_kg)}/kg</option>)}
              </select>
            </div>
            <div>
              <label className="mono-label">Berat (kg)</label>
              <input data-testid="sale-weight" type="number" className="field tap w-full px-4 mt-2"
                value={form.weight_kg} onChange={(e) => setForm({ ...form, weight_kg: e.target.value })} />
            </div>
            <div>
              <label className="mono-label">Harga Lelang / kg (opsional)</label>
              <input data-testid="sale-price" type="number" className="field tap w-full px-4 mt-2"
                placeholder={selFish ? `default ${selFish.price_per_kg}` : "harga pasar"}
                value={form.price_per_kg} onChange={(e) => setForm({ ...form, price_per_kg: e.target.value })} />
            </div>
          </div>

          <div className="mt-5">
            <label className="mono-label">Metode Pembayaran</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
              <button type="button" data-testid="pay-cash"
                onClick={() => setForm({ ...form, payment_method: "CASH" })}
                className={`text-left border p-4 transition-colors ${form.payment_method === "CASH" ? "border-[var(--ink)] bg-[var(--lavender)]" : "hairline"}`}>
                <Banknote size={18} />
                <p className="font-semibold mt-2">Pembayaran Tunai</p>
                <p className="text-sm text-[var(--muted)]">Cash penuh ke nelayan.</p>
              </button>
              <button type="button" data-testid="pay-potong"
                onClick={() => setForm({ ...form, payment_method: "POTONG_UTANG" })}
                className={`text-left border p-4 transition-colors ${form.payment_method === "POTONG_UTANG" ? "border-[var(--ink)] bg-[var(--lavender)]" : "hairline"}`}>
                <Scissors size={18} />
                <p className="font-semibold mt-2">Potong Utang Modal</p>
                <p className="text-sm text-[var(--muted)]">Tebasan/Ijon — kurangi utang dulu, sisa tunai.</p>
              </button>
            </div>
          </div>

          <div className="border hairline lav p-4 mt-5 flex flex-wrap gap-x-8 gap-y-2 text-sm">
            <span>Bruto: <b>{fmtRp(gross)}</b></span>
            {form.payment_method === "POTONG_UTANG" && selVessel && (
              <>
                <span>Dipotong utang: <b className="text-[var(--danger)]">{fmtRp(Math.min(gross, selVessel.owner_outstanding))}</b></span>
                <span>Tunai diterima: <b className="text-[var(--ok)]">{fmtRp(Math.max(0, gross - selVessel.owner_outstanding))}</b></span>
              </>
            )}
            {form.payment_method === "CASH" && <span>Tunai diterima: <b className="text-[var(--ok)]">{fmtRp(gross)}</b></span>}
          </div>

          {err && <p className="text-[var(--danger)] text-sm mt-3">{err}</p>}
          <button data-testid="sale-submit" onClick={submit} disabled={!form.vessel_id || !form.fish_id || !form.weight_kg}
            className="tap btn-primary px-6 font-semibold mt-5 disabled:opacity-40">Catat Lelang</button>
        </div>
      )}

      {sales.length === 0 ? <Empty>Belum ada transaksi lelang ikan.</Empty> : (
        <div className="border hairline divide-y divide-[var(--line)]">
          {sales.map((s) => (
            <div key={s.sale_id} data-testid="sale-row" className="p-5 flex flex-col sm:flex-row sm:items-center gap-4">
              <div className="w-10 h-10 bg-[var(--lavender)] flex items-center justify-center shrink-0"><Fish size={18} /></div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold">{s.fish_name} · {s.weight_kg} kg</span>
                  <Badge tone={s.payment_method === "CASH" ? "ok" : "ink"}>
                    {s.payment_method === "CASH" ? "Tunai" : "Potong Utang"}
                  </Badge>
                </div>
                <p className="text-sm text-[var(--muted)] mt-1">
                  {isStaff ? `${s.fisherman_name} · ` : ""}{fmtRp(s.price_per_kg)}/kg · oleh {s.recorded_by_name}
                </p>
                {s.amount_deducted > 0 && <p className="text-sm mt-1">Potong utang: <b className="text-[var(--danger)]">{fmtRp(s.amount_deducted)}</b></p>}
              </div>
              <div className="text-right">
                <p className="swiss-display text-xl">{fmtRp(s.gross_amount)}</p>
                <p className="mono-label">Tunai {fmtRp(s.cash_paid)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
