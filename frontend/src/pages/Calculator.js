import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Calculator as Calc, History } from "lucide-react";
import api, { fmtRp } from "@/lib/api";
import { PageHeader, Empty } from "@/components/ui-kit";

export default function Calculator() {
  const [fish, setFish] = useState([]);
  const [fishId, setFishId] = useState("");
  const [weight, setWeight] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  const load = useCallback(() => {
    api.get("/fish-prices").then((r) => setFish(r.data)).catch(() => {});
    api.get("/fish-calc/history").then((r) => setHistory(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const calc = async () => {
    try {
      const res = await api.post("/fish-calc", { fish_id: fishId, weight_kg: parseFloat(weight) });
      setResult(res.data);
      load();
    } catch { alert("Gagal menghitung"); }
  };

  return (
    <div data-testid="calculator-page">
      <PageHeader kicker="Layanan Usaha Koperasi" title="Kalkulator Ikan"
        desc="Simulasikan estimasi pendapatan bersih setelah bagi hasil koperasi." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-[var(--line)] border hairline">
        <div className="bg-white p-8">
          <div className="flex items-center gap-2 mb-6"><Calc size={18} /><span className="mono-label">Input Tangkapan</span></div>
          <label className="mono-label">Jenis Ikan</label>
          <select data-testid="calc-fish" className="field tap w-full px-4 mt-2 mb-5" value={fishId} onChange={(e) => setFishId(e.target.value)}>
            <option value="">— Pilih jenis ikan —</option>
            {fish.map((f) => <option key={f.fish_id} value={f.fish_id}>{f.name} — {fmtRp(f.price_per_kg)}/kg</option>)}
          </select>
          <label className="mono-label">Berat (kg)</label>
          <input data-testid="calc-weight" type="number" className="field tap w-full px-4 mt-2 mb-6" value={weight} onChange={(e) => setWeight(e.target.value)} />
          <button data-testid="calc-submit" onClick={calc} disabled={!fishId || !weight} className="tap btn-primary w-full font-semibold disabled:opacity-40">Hitung Estimasi</button>
        </div>

        <div className="bg-white p-8">
          <span className="mono-label">Hasil Estimasi</span>
          {result ? (
            <motion.div data-testid="calc-result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-6">
              <p className="mono-label">Pendapatan Bersih</p>
              <p className="swiss-display text-5xl mt-2">{fmtRp(result.net_income)}</p>
              <div className="mt-8 space-y-3 text-sm">
                <Row l={`Bruto (${result.weight_kg} kg × ${fmtRp(result.price_per_kg)})`} v={fmtRp(result.gross)} />
                <Row l={`Bagi hasil koperasi (${result.profit_sharing_percent}%)`} v={`− ${fmtRp(result.coop_cut)}`} muted />
                <div className="h-px bg-[var(--line)]" />
                <Row l="Diterima nelayan" v={fmtRp(result.net_income)} bold />
              </div>
            </motion.div>
          ) : (
            <div className="mt-6 border hairline border-dashed p-10 text-center text-[var(--muted)] text-sm">Hasil akan tampil di sini.</div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 mt-12 mb-4"><History size={16} /><span className="mono-label">Riwayat Perhitungan</span></div>
      {history.length === 0 ? <Empty>Belum ada riwayat.</Empty> : (
        <div className="border hairline divide-y divide-[var(--line)]">
          {history.map((h) => (
            <div key={h.calc_id} className="p-4 flex items-center justify-between text-sm">
              <span>{h.fish_name} · {h.weight_kg} kg</span>
              <span className="font-semibold">{fmtRp(h.net_income)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const Row = ({ l, v, muted, bold }) => (
  <div className="flex justify-between">
    <span className={muted ? "text-[var(--muted)]" : ""}>{l}</span>
    <span className={`tabular-nums ${bold ? "font-bold" : ""}`}>{v}</span>
  </div>
);
