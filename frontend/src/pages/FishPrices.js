import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Save, Percent } from "lucide-react";
import api, { fmtRp } from "@/lib/api";
import { PageHeader, Empty } from "@/components/ui-kit";

export default function FishPrices() {
  const [fish, setFish] = useState([]);
  const [form, setForm] = useState({ name: "", price_per_kg: "" });
  const [percent, setPercent] = useState("");
  const [bbm, setBbm] = useState(0);
  const [savedMsg, setSavedMsg] = useState("");

  const load = useCallback(() => {
    api.get("/fish-prices").then((r) => setFish(r.data)).catch(() => {});
    api.get("/settings/profit-sharing").then((r) => { setPercent(r.data.profit_sharing_percent); setBbm(r.data.bbm_price_per_liter); }).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.name || !form.price_per_kg) return;
    await api.post("/fish-prices", { name: form.name, price_per_kg: parseFloat(form.price_per_kg) });
    setForm({ name: "", price_per_kg: "" }); load();
  };
  const updatePrice = async (f, price) => {
    await api.put(`/fish-prices/${f.fish_id}`, { name: f.name, price_per_kg: parseFloat(price) }); load();
  };
  const del = async (id) => { await api.delete(`/fish-prices/${id}`); load(); };
  const saveSharing = async () => {
    await api.put("/settings/profit-sharing", { profit_sharing_percent: parseFloat(percent) });
    setSavedMsg("Tersimpan"); setTimeout(() => setSavedMsg(""), 1500);
  };

  return (
    <div data-testid="fish-prices-page">
      <PageHeader kicker="Konfigurasi Kalkulator" title="Harga Ikan & Bagi Hasil"
        desc="Kelola harga pasar per jenis ikan dan persentase bagi hasil koperasi." />

      <div className="border hairline p-4 sm:p-6 mb-8 flex flex-col sm:flex-row sm:items-end gap-4">
        <div className="flex-1">
          <label className="mono-label flex items-center gap-1"><Percent size={12} /> Bagi Hasil Koperasi (%)</label>
          <input data-testid="sharing-input" type="number" className="field tap w-full px-4 mt-2" value={percent} onChange={(e) => setPercent(e.target.value)} />
        </div>
        <div className="text-sm text-[var(--muted)]">Harga BBM subsidi: <b className="text-[var(--ink)]">{fmtRp(bbm)}/L</b></div>
        <button data-testid="sharing-save" onClick={saveSharing} className="tap btn-primary px-5 font-semibold flex items-center gap-2"><Save size={16} /> {savedMsg || "Simpan"}</button>
      </div>

      <div className="border hairline p-4 sm:p-6 mb-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="sm:col-span-1">
          <label className="mono-label">Nama Ikan</label>
          <input data-testid="fish-name" className="field tap w-full px-4 mt-2" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label className="mono-label">Harga / kg (Rp)</label>
          <input data-testid="fish-price" type="number" className="field tap w-full px-4 mt-2" value={form.price_per_kg} onChange={(e) => setForm({ ...form, price_per_kg: e.target.value })} />
        </div>
        <div className="flex items-end">
          <button data-testid="fish-add" onClick={add} className="tap btn-primary w-full font-semibold flex items-center justify-center gap-2"><Plus size={16} /> Tambah</button>
        </div>
      </div>

      {fish.length === 0 ? <Empty>Belum ada data harga ikan.</Empty> : (
        <div className="border hairline divide-y divide-[var(--line)]">
          {fish.map((f) => (
            <div key={f.fish_id} data-testid="fish-row" className="p-4 flex items-center gap-4">
              <span className="flex-1 font-semibold">{f.name}</span>
              <div className="flex items-center gap-1">
                <span className="mono-label">Rp</span>
                <input type="number" defaultValue={f.price_per_kg} onBlur={(e) => updatePrice(f, e.target.value)}
                  className="field w-32 px-3 py-2 text-right" data-testid="fish-price-edit" />
                <span className="mono-label">/kg</span>
              </div>
              <button data-testid="fish-delete" onClick={() => del(f.fish_id)} className="text-[var(--muted)] hover:text-[var(--danger)] p-2"><Trash2 size={16} /></button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
