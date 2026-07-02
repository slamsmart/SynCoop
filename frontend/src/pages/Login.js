import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Fingerprint, ArrowRight, Anchor, ShieldCheck } from "lucide-react";
import api, { ROLE_LABELS } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function startGoogleLogin() {
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

const DEMO_ROLES = ["NELAYAN", "PETUGAS_LAPANG", "ADMIN", "PETUGAS_DINAS"];

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [mode, setMode] = useState("main"); // main | pin
  const [pinEmail, setPinEmail] = useState("");
  const [pin, setPin] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const demoLogin = async (role) => {
    setBusy(true);
    try {
      const res = await api.post("/auth/demo", { role });
      setUser(res.data);
      navigate("/dashboard", { state: { user: res.data } });
    } catch {
      setErr("Gagal masuk demo");
    } finally {
      setBusy(false);
    }
  };

  const pinLogin = async () => {
    setErr("");
    setBusy(true);
    try {
      const res = await api.post("/auth/pin/login", { email: pinEmail, pin });
      setUser(res.data);
      navigate("/dashboard", { state: { user: res.data } });
    } catch (e) {
      setErr(e?.response?.data?.detail || "Email atau PIN salah");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12">
      {/* Left brand panel */}
      <div className="lg:col-span-7 border-b lg:border-b-0 lg:border-r hairline px-8 lg:px-16 py-12 lg:py-0 flex flex-col justify-between">
        <div className="flex items-center gap-3 pt-2">
          <div className="w-9 h-9 bg-[var(--ink)] text-white flex items-center justify-center">
            <Anchor size={18} />
          </div>
          <span className="mono-label !text-[var(--ink)]">SynCoop</span>
        </div>

        <div className="py-16 lg:py-0">
          <p className="mono-label mb-6">Ekosistem Manajemen Koperasi Nelayan</p>
          <h1 className="swiss-display text-5xl sm:text-6xl lg:text-7xl max-w-3xl">
            Kelola BBM<br />subsidi & kas<br />koperasi.<span className="text-[var(--muted)]"> Transparan.</span>
          </h1>
          <p className="text-[var(--muted)] text-lg mt-8 max-w-md">
            Distribusi BBM tepat sasaran, kalkulator hasil tangkapan, dan pembukuan
            utang yang adil untuk nelayan akar rumput.
          </p>
        </div>

        <div className="hidden lg:flex gap-10 pb-2 text-sm text-[var(--muted)]">
          <span className="flex items-center gap-2"><ShieldCheck size={15} /> Anti-spekulan</span>
          <span>Kuota 400 L / bulan</span>
          <span>Swiss Design System</span>
        </div>
      </div>

      {/* Right auth panel */}
      <div className="lg:col-span-5 px-8 lg:px-14 py-12 flex items-center">
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-sm mx-auto"
        >
          {mode === "main" && (
            <div data-testid="login-main">
              <p className="mono-label mb-2">Masuk</p>
              <h2 className="swiss-display text-3xl mb-8">Selamat datang.</h2>

              <button
                data-testid="google-login-btn"
                onClick={startGoogleLogin}
                className="tap w-full btn-primary flex items-center justify-center gap-3 font-semibold text-[15px] mb-3"
              >
                <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="" className="w-5 h-5 bg-white rounded-sm" />
                Masuk dengan Google
              </button>

              <button
                data-testid="pin-mode-btn"
                onClick={() => setMode("pin")}
                className="tap w-full btn-outline flex items-center justify-center gap-2 font-semibold text-[15px]"
              >
                <Fingerprint size={18} /> Masuk dengan PIN
              </button>

              <div className="flex items-center gap-3 my-8">
                <div className="h-px flex-1 bg-[var(--line)]" />
                <span className="mono-label">Akses Demo Cepat</span>
                <div className="h-px flex-1 bg-[var(--line)]" />
              </div>

              <div className="grid grid-cols-2 gap-2">
                {DEMO_ROLES.map((r) => (
                  <button
                    key={r}
                    data-testid={`demo-${r}-btn`}
                    disabled={busy}
                    onClick={() => demoLogin(r)}
                    className="text-left border hairline p-3 hover:bg-[var(--lavender)] transition-colors disabled:opacity-50"
                  >
                    <span className="block text-[13px] font-semibold leading-tight">{ROLE_LABELS[r]}</span>
                    <span className="mono-label flex items-center gap-1 mt-1">masuk <ArrowRight size={11} /></span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {mode === "pin" && (
            <div data-testid="login-pin">
              <p className="mono-label mb-2">Fallback</p>
              <h2 className="swiss-display text-3xl mb-8">Masuk dengan PIN.</h2>
              <label className="mono-label">Email</label>
              <input
                data-testid="pin-email-input"
                value={pinEmail} onChange={(e) => setPinEmail(e.target.value)}
                placeholder="email@anda.id"
                className="field tap w-full px-4 mt-2 mb-4 text-[15px]"
              />
              <label className="mono-label">PIN 6 Angka</label>
              <input
                data-testid="pin-input"
                value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric" placeholder="••••••"
                className="field tap w-full px-4 mt-2 mb-4 text-[15px] tracking-[0.5em]"
              />
              {err && <p className="text-[var(--danger)] text-sm mb-3" data-testid="pin-error">{err}</p>}
              <button
                data-testid="pin-submit-btn"
                disabled={busy}
                onClick={pinLogin}
                className="tap w-full btn-primary font-semibold text-[15px] disabled:opacity-50"
              >
                Masuk
              </button>
              <button onClick={() => { setMode("main"); setErr(""); }} className="mono-label mt-5 mx-auto block">
                ← Kembali
              </button>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
