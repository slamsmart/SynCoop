import { useEffect, useState, useCallback } from "react";
import { Plus, Ship, AlertTriangle } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Badge, Empty } from "@/components/ui-kit";

export default function Vessels() {
  const { user } = useAuth();
  const [vessels, setVessels] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ owner_email: "", vessel_name: "", vessel_type: "PAS_KECIL", rekom_number: "" });
  const [msg, setMsg] = useState("");

  const isDinas = user.role === "PETUGAS_DINAS" || user.role === "ADMIN";

  const load = useCallback(() => {
    api.get("/vessels").then((r) => setVessels(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    setMsg("");
    try {
      await api.post("/vessels", form);
      setShowForm(false);
      setForm({ owner_email: "", vessel_name: "", vessel_type: "PAS_KECIL", rekom_number: "" });
      load();
    } catch (e) {
      setMsg(e?.response?.data?.detail || "Gagal menyimpan");
    }
  };

  return (
    <div data-testid="vessels-page">
      <PageHeader
        kicker={isDinas ? "Surat Rekomendasi BBM" : "Armada & Kuota"}
        title={isDinas ? "Surat Rekomendasi" : "Perahu & Kuota"}
        desc={isDinas ? "Daftarkan perahu nelayan beserta limit kuota 400 L/bulan." : "Pantau sisa kuota BBM bersubsidi setiap perahu Anda."}
        action={user.role === "PETUGAS_DINAS" || user.role === "ADMIN" ? (
          <button data-testid="add-vessel-btn" onClick={() => setShowForm(!showForm)}
            className="tap btn-primary px-5 font-semibold flex items-center gap-2">
            <Plus size={18} /> Daftar Rekomendasi
          </button>
        ) : null}
      />

      {showForm && (
        <div data-testid="vessel-form" className="border hairline p-4 sm:p-6 mb-8 grid grid-cols-1 md:grid-cols-2 gap-4 fade-up">
          <div>
            <label className="mono-label">Email Pemilik (Nelayan)</label>
            <input data-testid="vf-owner" className="field tap w-full px-4 mt-2" placeholder="nelayan@demo.syncoop.id"
              value={form.owner_email} onChange={(e) => setForm({ ...form, owner_email: e.target.value })} />
          </div>
          <div>
            <label className="mono-label">Nama Perahu</label>
            <input data-testid="vf-name" className="field tap w-full px-4 mt-2"
              value={form.vessel_name} onChange={(e) => setForm({ ...form, vessel_name: e.target.value })} />
          </div>
          <div>
            <label className="mono-label">Jenis Pas</label>
            <select data-testid="vf-type" className="field tap w-full px-4 mt-2"
              value={form.vessel_type} onChange={(e) => setForm({ ...form, vessel_type: e.target.value })}>
              <option value="PAS_KECIL">Pas Kecil</option>
              <option value="PAS_BESAR">Pas Besar</option>
            </select>
          </div>
          <div>
            <label className="mono-label">No. Surat Rekomendasi</label>
            <input data-testid="vf-rekom" className="field tap w-full px-4 mt-2" placeholder="REK/2026/00X"
              value={form.rekom_number} onChange={(e) => setForm({ ...form, rekom_number: e.target.value })} />
          </div>
          {msg && <p className="text-[var(--danger)] text-sm md:col-span-2">{msg}</p>}
          <div className="md:col-span-2">
            <button data-testid="vf-submit" onClick={create} className="tap btn-primary px-6 font-semibold">Simpan</button>
          </div>
        </div>
      )}

      {vessels.length === 0 ? (
        <Empty>Belum ada perahu terdaftar.</Empty>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-px bg-[var(--line)] border hairline">
          {vessels.map((v) => {
            const pct = Math.min(100, (v.used_quota / v.monthly_quota_max) * 100);
            const low = v.remaining_quota <= 50;
            return (
              <div key={v.vessel_id} data-testid="vessel-card" className="bg-white p-5 sm:p-6">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Ship size={18} />
                    <span className="font-semibold">{v.vessel_name}</span>
                  </div>
                  <Badge tone={v.vessel_type === "PAS_BESAR" ? "ink" : "lav"}>
                    {v.vessel_type === "PAS_BESAR" ? "Pas Besar" : "Pas Kecil"}
                  </Badge>
                </div>
                <p className="mono-label mt-2">{v.rekom_number}</p>
                {isDinas && <p className="text-sm text-[var(--muted)] mt-1">{v.owner_name}</p>}

                <div className="mt-5">
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-[var(--muted)]">Kuota bulan ini</span>
                    <span className="font-semibold tabular-nums">{v.used_quota} / {v.monthly_quota_max} L</span>
                  </div>
                  <div className="h-2 bg-[var(--lavender)]">
                    <div className={`h-2 ${low ? "bg-[var(--danger)]" : "bg-[var(--ink)]"}`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="flex items-center gap-1 mt-3">
                    {low && <AlertTriangle size={14} className="text-[var(--danger)]" />}
                    <span className={`text-sm font-semibold ${low ? "text-[var(--danger)]" : ""}`}>
                      Sisa {v.remaining_quota} L
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
