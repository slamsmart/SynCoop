import { useEffect, useState } from "react";
import {
  Anchor, ArrowRight, Download, Fish, Fuel,
  MessageSquareText, ReceiptText, ShieldCheck, Ship, Users,
} from "lucide-react";
import api, { API, fmtRp } from "@/lib/api";
import { Badge } from "@/components/ui-kit";

function startGoogleLogin() {
  window.location.href = `${API}/auth/google/start?redirect=${encodeURIComponent("/dashboard")}`;
}

const DEFAULT_PORTAL = {
  hero_kicker: "Ekosistem Manajemen Koperasi Nelayan",
  hero_heading: "Koperasi nelayan yang transparan dan dekat.",
  hero_description: "Kelola BBM subsidi & kas koperasi secara transparan. Distribusi BBM tepat sasaran, kalkulator hasil tangkapan, dan pembukuan utang yang adil untuk nelayan akar rumput.",
  stat_cards: [
    { key: "members", label: "Anggota Bergabung", icon: "Users" },
    { key: "transaction_value", label: "Perputaran Transaksi", icon: "ReceiptText" },
    { key: "fuel_liters", label: "Penyaluran BBM Kapal Nelayan", icon: "Fuel" },
    { key: "vessels", label: "Kapal Rekom BBM", icon: "Ship" },
  ],
};
const STAT_ICONS = { Users, ReceiptText, Fuel, Ship };

function statValue(key, stats) {
  if (key === "transaction_value") return fmtRp(stats.transaction_value || 0);
  if (key === "fuel_liters") return `${Number(stats.fuel_liters || 0).toLocaleString("id-ID", { maximumFractionDigits: 0 })} L`;
  return stats[key] || 0;
}

function statSub(key, stats) {
  if (key === "transaction_value") return `${stats.transactions || 0} transaksi`;
  return "";
}

export default function PublicPortal() {
  const [data, setData] = useState({ stats: {}, portal: DEFAULT_PORTAL, fish_prices: [], announcements: [] });
  const [form, setForm] = useState({ contact_name: "", contact_phone: "", category: "Pendaftaran Anggota", subject: "", message: "" });
  const [sent, setSent] = useState("");
  const [installPrompt, setInstallPrompt] = useState(null);

  useEffect(() => {
    api.get("/public/portal").then((r) => setData(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const onBeforeInstallPrompt = (event) => {
      event.preventDefault();
      setInstallPrompt(event);
    };
    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
  }, []);

  const installApp = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice.catch(() => {});
    setInstallPrompt(null);
  };

  const submit = async () => {
    try {
      const res = await api.post("/public/tickets", form);
      setSent(`Tiket terkirim: ${res.data.ticket_id}`);
      setForm({ contact_name: "", contact_phone: "", category: "Pendaftaran Anggota", subject: "", message: "" });
    } catch { setSent("Gagal mengirim tiket"); }
  };
  const portal = { ...DEFAULT_PORTAL, ...(data.portal || {}) };

  return (
    <div className="min-h-screen bg-white">
      <header className="min-h-16 px-4 sm:px-6 lg:px-12 py-3 border-b hairline flex items-center justify-between gap-3 sticky top-0 bg-white/95 z-20">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-[var(--sea)] text-white flex items-center justify-center"><Anchor size={18} /></div>
          <div><p className="font-extrabold leading-none">SynCoop</p><p className="mono-label">Koperasi Digital Nelayan</p></div>
        </div>
        {installPrompt && (
          <button onClick={installApp} className="btn-outline px-3 py-2 text-sm font-semibold hidden sm:flex items-center gap-2">
            <Download size={15} /> Install
          </button>
        )}
      </header>

      <main>
        <section className="px-4 sm:px-6 lg:px-12 py-10 sm:py-12 lg:py-16 border-b hairline bg-[linear-gradient(135deg,#F8FFFD_0%,#FFFFFF_60%,#EEF8F5_100%)]">
          <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            <div data-reveal>
              <p className="mono-label mb-4">{portal.hero_kicker}</p>
              <h1 className="swiss-display text-4xl sm:text-5xl lg:text-7xl">
                {portal.hero_heading}
              </h1>
              <p className="text-[var(--muted)] text-lg mt-6 max-w-xl">
                {portal.hero_description}
              </p>
              <div className="flex flex-wrap gap-3 mt-8">
                <button
                  type="button"
                  onClick={startGoogleLogin}
                  className="tap btn-primary px-5 font-semibold flex items-center gap-2"
                >
                  DAFTAR <ArrowRight size={16} />
                </button>
                <a href="#layanan" className="tap btn-outline px-5 font-semibold flex items-center gap-2">Ajukan Layanan</a>
              </div>
              <p className="text-sm text-[var(--muted)] mt-3">Menggunakan Gmail lebih cepat, lewat credential OAuth Google.</p>
            </div>
            <div data-reveal style={{ "--reveal-delay": "120ms" }}>
              <LoginPanel installPrompt={installPrompt} onInstall={installApp} />
            </div>
          </div>
        </section>

        <section className="px-4 sm:px-6 lg:px-12 py-10 max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-10">
          <div data-reveal>
            <div className="flex items-center gap-2 mb-4"><Fish size={18} /><h2 className="font-bold text-xl">Harga Ikan Hari Ini</h2></div>
            <div className="border hairline divide-y divide-[var(--line)]">
              {data.fish_prices.map((f) => (
                <div key={f.fish_id} data-reveal className="p-4 flex items-center justify-between">
                  <p className="font-semibold">{f.name}</p>
                  <p className="font-bold">{fmtRp(f.price_per_kg)} / kg</p>
                </div>
              ))}
            </div>
          </div>
          <div data-reveal style={{ "--reveal-delay": "100ms" }}>
            <div className="flex items-center gap-2 mb-4"><ShieldCheck size={18} /><h2 className="font-bold text-xl">Pengumuman</h2></div>
            <div className="border hairline divide-y divide-[var(--line)]">
              {data.announcements.map((a) => (
                <div key={a.announcement_id} data-reveal className="p-4">
                  <Badge tone="lav">Publik</Badge>
                  <p className="font-semibold mt-3">{a.title}</p>
                  <p className="text-sm text-[var(--muted)] mt-1">{a.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="layanan" className="px-4 sm:px-6 lg:px-12 py-10 border-t hairline">
          <div className="max-w-3xl mx-auto" data-reveal>
            <div className="flex items-center gap-2 mb-4"><MessageSquareText size={18} /><h2 className="font-bold text-xl">Ajukan Layanan</h2></div>
            <div className="border hairline p-5 grid grid-cols-1 md:grid-cols-2 gap-3">
              <input className="field tap px-4" placeholder="Nama" value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
              <input className="field tap px-4" placeholder="No. HP" value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
              <select className="field tap px-4 md:col-span-2" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option>Pendaftaran Anggota</option><option>Keluhan Warga</option><option>Harga Ikan</option><option>Layanan Koperasi</option>
              </select>
              <input className="field tap px-4 md:col-span-2" placeholder="Subjek" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
              <textarea className="field px-4 py-3 md:col-span-2" rows={4} placeholder="Pesan" value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} />
              {sent && <p className="text-sm md:col-span-2">{sent}</p>}
              <button disabled={!form.contact_name || !form.subject || !form.message} onClick={submit} className="tap btn-primary font-semibold md:col-span-2 disabled:opacity-40">Kirim ke Koperasi</button>
            </div>
          </div>
        </section>

        <footer className="px-4 sm:px-6 lg:px-12 py-10 border-t hairline bg-white">
          <div className="max-w-6xl mx-auto" data-reveal>
            <p className="mono-label mb-4">Dampak Koperasi</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-[var(--line)] border hairline">
              {(portal.stat_cards || DEFAULT_PORTAL.stat_cards).map((card) => (
                <Metric
                  key={card.key}
                  icon={card.icon}
                  label={card.label}
                  value={statValue(card.key, data.stats)}
                  sub={statSub(card.key, data.stats)}
                />
              ))}
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}

function LoginPanel({ installPrompt, onInstall }) {
  return (
    <div className="bg-white border hairline p-5 sm:p-6 lg:p-8 shadow-[0_24px_80px_rgba(11,11,11,0.06)]">
      <div className="mb-6">
        <p className="mono-label mb-2">Daftar / Masuk</p>
        <h2 className="swiss-display text-3xl sm:text-4xl leading-none">Mulai dengan Gmail.</h2>
        <p className="text-sm text-[var(--muted)] mt-3">
          Akun baru otomatis dibuat saat pertama kali masuk dengan OAuth Google.
        </p>
      </div>

      <button
        onClick={startGoogleLogin}
        className="tap w-full btn-primary flex items-center justify-center gap-3 font-semibold text-[15px] mb-3"
      >
        <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="" className="w-5 h-5 bg-white rounded-sm" />
        DAFTAR dengan Gmail
      </button>

      {installPrompt && (
        <button onClick={onInstall} className="tap w-full btn-outline flex sm:hidden items-center justify-center gap-2 font-semibold text-[15px] mt-3">
          <Download size={18} /> Install SynCoop
        </button>
      )}
    </div>
  );
}

function Metric({ icon, label, value, sub }) {
  const Icon = STAT_ICONS[icon] || ShieldCheck;
  return (
    <div className="bg-white p-5 sm:p-6" data-reveal>
      <div className="flex items-center gap-2">
        <Icon size={17} className="text-[var(--sea)] shrink-0" />
        <p className="mono-label">{label}</p>
      </div>
      <p className="swiss-display text-3xl sm:text-4xl mt-4">{value}</p>
      {sub && <p className="text-sm text-[var(--muted)] mt-2">{sub}</p>}
    </div>
  );
}
