import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { History, Scale } from "lucide-react";
import api, { fmtRp } from "@/lib/api";
import { PageHeader, Empty } from "@/components/ui-kit";

const QUICK_KG = [1, 5, 10, 25];

export default function Calculator() {
  const [fish, setFish] = useState([]);
  const [fishId, setFishId] = useState("");
  const [weight, setWeight] = useState("");
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.get("/fish-prices").then((r) => setFish(r.data)).catch(() => {});
    api.get("/fish-calc/history").then((r) => setHistory(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const calc = async () => {
    setErr("");
    setBusy(true);
    try {
      const res = await api.post("/fish-calc", { fish_id: fishId, weight_kg: parseFloat(weight) });
      setResult(res.data);
      load();
    } catch (e) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === "string" ? d : "Gagal menghitung. Pilih jenis ikan & isi berat dulu.");
    } finally {
      setBusy(false);
    }
  };

  const addKg = (n) => setWeight(String((parseFloat(weight) || 0) + n));

  return (
    <div data-testid="calculator-page" className="max-w-2xl mx-auto lg:mx-0">
      <PageHeader kicker="Layanan Usaha Koperasi" title="Hitung Hasil Tangkapan"
        desc="Ketuk jenis ikan, isi berat, langsung tahu uang yang Anda terima." />

      {/* Step 1: pilih ikan */}
      <p className="mono-label mb-2">1 · Ketuk Jenis Ikan</p>
      {fish.length === 0 ? <Empty>Belum ada harga ikan dari koperasi.</Empty> : (
        <div className="grid grid-cols-2 gap-2 mb-6">
          {fish.map((f) => (
            <button
              key={f.fish_id}
              data-testid={`fish-chip-${f.fish_id}`}
              onClick={() => setFishId(f.fish_id)}
              className={`text-left border p-3.5 min-h-[68px] transition-colors ${
                fishId === f.fish_id ? "border-[var(--ink)] bg-[var(--ink)] text-white" : "hairline bg-white hover:bg-[var(--lavender)]"
              }`}
            >
              <span className="block font-bold text-[15px] leading-tight">{f.name}</span>
              <span className={`block text-[13px] mt-1 ${fishId === f.fish_id ? "text-white/80" : "text-[var(--muted)]"}`}>
                {fmtRp(f.price_per_kg)}/kg
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Step 2: berat */}
      <p className="mono-label mb-2">2 · Berat Tangkapan (kg)</p>
      <div className="flex items-center gap-2 mb-2">
        <div className="relative flex-1">
          <Scale size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted)]" />
          <input
            data-testid="calc-weight"
            type="number" inputMode="decimal" placeholder="0"
            className="field tap w-full pl-11 pr-4 text-2xl font-bold tabular-nums"
            value={weight} onChange={(e) => setWeight(e.target.value)}
          />
        </div>
        <span className="font-bold text-lg">kg</span>
      </div>
      <div className="flex gap-2 mb-6">
        {QUICK_KG.map((n) => (
          <button key={n} data-testid={`quick-kg-${n}`} onClick={() => addKg(n)}
            className="flex-1 border hairline py-2.5 font-bold text-[14px] hover:bg-[var(--lavender)] transition-colors">
            +{n}
          </button>
        ))}
        <button onClick={() => setWeight("")} className="flex-1 border hairline py-2.5 text-[13px] font-semibold text-[var(--muted)]">
          Hapus
        </button>
      </div>

      <button data-testid="calc-submit" onClick={calc} disabled={!fishId || !weight || busy}
        className="tap btn-primary w-full font-bold text-[17px] disabled:opacity-40 mb-3">
        {busy ? "Menghitung…" : "Hitung Sekarang"}
      </button>
      {err && <p data-testid="calc-error" className="text-[var(--danger)] text-sm mb-3">{err}</p>}

      {/* Hasil */}
      {result && (
        <motion.div data-testid="calc-result" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          className="border-2 border-[var(--ink)] p-6 mt-4 bg-white">
          <p className="mono-label">Uang yang Anda Terima</p>
          <p className="swiss-display text-4xl sm:text-5xl mt-2 text-[var(--ok)]">{fmtRp(result.net_income)}</p>
          <div className="mt-6 space-y-3 text-[14px]">
            <Row l={`Hasil kotor (${result.weight_kg} kg × ${fmtRp(result.price_per_kg)})`} v={fmtRp(result.gross)} />
            <Row l={`Potongan koperasi (${result.profit_sharing_percent}%)`} v={`− ${fmtRp(result.coop_cut)}`} muted />
            <div className="h-px bg-[var(--line)]" />
            <Row l="Bersih diterima" v={fmtRp(result.net_income)} bold />
          </div>
        </motion.div>
      )}

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
  <div className="flex justify-between gap-3">
    <span className={muted ? "text-[var(--muted)]" : ""}>{l}</span>
    <span className={`tabular-nums whitespace-nowrap ${bold ? "font-bold" : ""}`}>{v}</span>
  </div>
);
