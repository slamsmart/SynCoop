import { useEffect, useState, useCallback } from "react";
import { Bell, MessageSquarePlus, Wallet } from "lucide-react";
import api, { fmtRp } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, Badge, Empty } from "@/components/ui-kit";

export default function Debts() {
  const { user } = useAuth();
  const isStaff = user.role === "ADMIN" || user.role === "PETUGAS_LAPANG";

  if (isStaff) return <MasterSheet isAdmin={user.role === "ADMIN"} />;
  return <MyDebts />;
}

function MasterSheet({ isAdmin }) {
  const [data, setData] = useState({ items: [], total_outstanding: 0, count: 0 });
  const load = useCallback(() => {
    api.get("/debts/master").then((r) => setData(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const remind = async (id) => {
    try { await api.post(`/transactions/${id}/remind`); alert("Pengingat terkirim ke nelayan."); }
    catch { alert("Gagal"); }
  };

  return (
    <div data-testid="debts-master-page">
      <PageHeader kicker="Lembar Induk Piutang" title="Master Piutang"
        desc="Agregasi seluruh nelayan dengan status kurang bayar beserta alasan penundaan." />
      <div className="grid grid-cols-2 gap-px bg-[var(--line)] border hairline mb-8">
        <div className="bg-white"><StatCard label="Total Piutang" value={fmtRp(data.total_outstanding)} danger={data.total_outstanding > 0} /></div>
        <div className="bg-white"><StatCard label="Jumlah Penunggak" value={data.count} index={1} /></div>
      </div>

      {data.items.length === 0 ? <Empty>Tidak ada piutang aktif. 🎉</Empty> : (
        <div className="border hairline divide-y divide-[var(--line)]">
          {data.items.map((t) => (
            <div key={t.transaction_id} data-testid="debt-row" className="p-5 flex flex-col lg:flex-row lg:items-center gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold">{t.fisherman_name}</span>
                  <Badge tone="outline">{t.vessel_name}</Badge>
                </div>
                <p className="text-sm text-[var(--muted)] mt-1">{t.liters_bought} L · Total {fmtRp(t.total_price)} · Dibayar {fmtRp(t.amount_paid)}</p>
                <p className="text-sm mt-2">
                  <span className="mono-label">Alasan: </span>
                  {t.debt_reason ? <span className="lav px-2 py-0.5">{t.debt_reason}</span> : <span className="text-[var(--muted)] italic">belum diisi nelayan</span>}
                </p>
              </div>
              <div className="text-right flex lg:flex-col items-end gap-3">
                <p className="swiss-display text-2xl text-[var(--danger)]">{fmtRp(t.remaining_balance)}</p>
                {isAdmin && (
                  <button data-testid="remind-btn" onClick={() => remind(t.transaction_id)}
                    className="btn-outline px-3 py-1.5 text-sm font-semibold flex items-center gap-1">
                    <Bell size={14} /> Kirim Pengingat
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MyDebts() {
  const [trx, setTrx] = useState([]);
  const [editing, setEditing] = useState(null);
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    api.get("/transactions").then((r) => setTrx(r.data.filter((t) => t.remaining_balance > 0))).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveReason = async (id) => {
    try { await api.post(`/transactions/${id}/debt-reason`, { reason }); setEditing(null); setReason(""); load(); }
    catch { alert("Gagal menyimpan alasan"); }
  };

  const total = trx.reduce((s, t) => s + t.remaining_balance, 0);

  return (
    <div data-testid="my-debts-page">
      <PageHeader kicker="Portal Transparansi" title="Utang Saya"
        desc="Lihat sisa kurang bayar Anda. Wajib mengisi alasan penundaan pembayaran." />
      <div className="border hairline p-6 mb-8 flex items-center gap-4">
        <div className="w-12 h-12 bg-[var(--ink)] text-white flex items-center justify-center"><Wallet size={22} /></div>
        <div>
          <p className="mono-label">Total Kurang Bayar</p>
          <p className="swiss-display text-3xl text-[var(--danger)]">{fmtRp(total)}</p>
        </div>
      </div>

      {trx.length === 0 ? <Empty>Tidak ada utang. Anda lunas! 🎉</Empty> : (
        <div className="space-y-px bg-[var(--line)] border hairline">
          {trx.map((t) => (
            <div key={t.transaction_id} data-testid="my-debt-row" className="bg-white p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-semibold">{t.vessel_name} · {t.liters_bought} L</p>
                  <p className="text-sm text-[var(--muted)] mt-1">Total {fmtRp(t.total_price)} · Dibayar {fmtRp(t.amount_paid)}</p>
                </div>
                <p className="swiss-display text-2xl text-[var(--danger)]">{fmtRp(t.remaining_balance)}</p>
              </div>

              {editing === t.transaction_id ? (
                <div className="mt-4">
                  <textarea data-testid="reason-input" rows={2} className="field w-full px-4 py-3" placeholder="Cth: cuaca buruk, mesin perahu rusak…"
                    value={reason} onChange={(e) => setReason(e.target.value)} />
                  <div className="flex gap-2 mt-2">
                    <button data-testid="reason-save" onClick={() => saveReason(t.transaction_id)} className="btn-primary px-4 py-2 text-sm font-semibold">Simpan</button>
                    <button onClick={() => setEditing(null)} className="btn-outline px-4 py-2 text-sm font-semibold">Batal</button>
                  </div>
                </div>
              ) : (
                <div className="mt-3 flex items-center gap-3">
                  {t.debt_reason ? <span className="lav px-2 py-1 text-sm">Alasan: {t.debt_reason}</span> : <span className="text-sm text-[var(--muted)] italic">Alasan belum diisi</span>}
                  <button data-testid="add-reason-btn" onClick={() => { setEditing(t.transaction_id); setReason(t.debt_reason || ""); }}
                    className="mono-label flex items-center gap-1"><MessageSquarePlus size={13} /> {t.debt_reason ? "ubah" : "isi alasan"}</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
