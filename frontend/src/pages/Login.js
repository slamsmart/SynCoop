import { useState } from "react";
import { motion } from "framer-motion";
import { Anchor, ShieldCheck } from "lucide-react";
import { API } from "@/lib/api";

function startGoogleLogin() {
  window.location.href = `${API}/auth/google/start?redirect=${encodeURIComponent("/dashboard")}`;
}

export default function Login() {
  const [busy, setBusy] = useState(false);

  const continueWithGoogle = () => {
    setBusy(true);
    startGoogleLogin();
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12">
      <div className="lg:col-span-7 border-b lg:border-b-0 lg:border-r hairline px-4 sm:px-8 lg:px-16 py-10 lg:py-0 flex flex-col justify-between">
        <div className="flex items-center gap-3 pt-2">
          <div className="w-9 h-9 bg-[var(--ink)] text-white flex items-center justify-center">
            <Anchor size={18} />
          </div>
          <span className="mono-label !text-[var(--ink)]">SynCoop</span>
        </div>

        <div className="py-16 lg:py-0">
          <p className="mono-label mb-6">Ekosistem Manajemen Koperasi Nelayan</p>
          <h1 className="swiss-display text-4xl sm:text-6xl lg:text-7xl max-w-3xl">
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

      <div className="lg:col-span-5 px-4 sm:px-8 lg:px-14 py-10 sm:py-12 flex items-center">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md mx-auto"
        >
          <div data-testid="login-main">
            <p className="mono-label mb-2">Daftar / Masuk</p>
            <h2 className="swiss-display text-3xl mb-3">Mulai dengan Gmail.</h2>
            <p className="text-sm text-[var(--muted)] mb-6">
              Akun baru otomatis dibuat saat pertama kali masuk dengan OAuth Google.
            </p>

            <button
              data-testid="google-login-btn"
              onClick={continueWithGoogle}
              disabled={busy}
              className="tap w-full btn-primary flex items-center justify-center gap-3 font-semibold text-[15px] disabled:opacity-50"
            >
              <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="" className="w-5 h-5 bg-white rounded-sm" />
              {busy ? "Mengalihkan..." : "Lanjutkan dengan Gmail"}
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
