import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Fingerprint, Lock, ShieldCheck, Clock } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Badge } from "@/components/ui-kit";

function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function stringToBuffer(value) {
  return new TextEncoder().encode(value);
}

function useCountdown(status) {
  const [secs, setSecs] = useState(status?.seconds_remaining || 0);
  useEffect(() => {
    if (!status) return;
    setSecs(status.seconds_remaining);
    if (status.is_matured) return;
    const t = setInterval(() => setSecs((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [status]);
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return { d, h, m, s, secs };
}

export default function Membership() {
  const { user, checkAuth } = useAuth();
  const [status, setStatus] = useState(null);
  const [form, setForm] = useState({ nik: "", phone: "", address: "" });
  const [msg, setMsg] = useState("");
  const [bioMsg, setBioMsg] = useState("");
  const [bioBusy, setBioBusy] = useState(false);
  const cd = useCountdown(status);

  const load = useCallback(() => {
    api.get("/membership/status").then((r) => setStatus(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const submitKyc = async () => {
    setMsg("");
    try {
      await api.post("/kyc/submit", form);
      setMsg("KYC berhasil dikirim, menunggu persetujuan admin.");
      load(); checkAuth();
    } catch (e) {
      setMsg(e?.response?.data?.detail || "Gagal mengirim KYC");
    }
  };

  const matured = status?.is_matured;
  const kyc = status?.kyc_status;
  const biometricSupported = typeof window !== "undefined" && Boolean(window.PublicKeyCredential);

  const enableBiometric = async () => {
    setBioMsg("");
    if (!biometricSupported) {
      setBioMsg("Browser/perangkat ini belum mendukung biometric passkey.");
      return;
    }
    setBioBusy(true);
    try {
      const challenge = crypto.getRandomValues(new Uint8Array(32));
      const credential = await navigator.credentials.create({
        publicKey: {
          challenge,
          rp: { name: "SynCoop" },
          user: {
            id: stringToBuffer(user.user_id || user.email),
            name: user.email,
            displayName: user.name || user.email,
          },
          pubKeyCredParams: [{ type: "public-key", alg: -7 }, { type: "public-key", alg: -257 }],
          authenticatorSelection: {
            authenticatorAttachment: "platform",
            userVerification: "required",
            residentKey: "required",
            requireResidentKey: true,
          },
          timeout: 60000,
          attestation: "none",
        },
      });
      await api.post("/auth/biometric/register", {
        credential_id: bufferToBase64url(credential.rawId),
        device_name: navigator.userAgent.includes("Windows") ? "Windows Hello" : "Perangkat ini",
      });
      await checkAuth();
      setBioMsg("Biometric/passkey aktif untuk akun ini.");
    } catch (e) {
      setBioMsg(e?.response?.data?.detail || "Aktivasi biometric dibatalkan atau gagal.");
    } finally {
      setBioBusy(false);
    }
  };

  const disableBiometric = async () => {
    setBioBusy(true);
    setBioMsg("");
    try {
      await api.post("/auth/biometric/disable");
      await checkAuth();
      setBioMsg("Biometric/passkey dinonaktifkan.");
    } catch {
      setBioMsg("Gagal menonaktifkan biometric.");
    } finally {
      setBioBusy(false);
    }
  };

  return (
    <div data-testid="membership-page">
      <PageHeader kicker="Anti-Speculation Engine" title="Keanggotaan"
        desc="Masa tunggu 365 hari menjaga kas koperasi dari anggota musiman. KYC terbuka setelah masa tunggu selesai." />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-[var(--line)] border hairline">
        {/* Countdown */}
        <div className="bg-white p-5 sm:p-8">
          <div className="flex items-center gap-2 mb-6">
            {matured ? <ShieldCheck size={18} className="text-[var(--ok)]" /> : <Clock size={18} />}
            <span className="mono-label">{matured ? "Masa tunggu selesai" : "Hitung mundur maturitas"}</span>
          </div>

          {!matured ? (
            <>
              <div data-testid="countdown" className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-[var(--line)] border hairline">
                {[["HARI", cd.d], ["JAM", cd.h], ["MNT", cd.m], ["DTK", cd.s]].map(([l, v]) => (
                  <div key={l} className="bg-white py-6 text-center">
                    <div className="swiss-display text-4xl tabular-nums">{String(v).padStart(2, "0")}</div>
                    <div className="mono-label mt-2">{l}</div>
                  </div>
                ))}
              </div>
              <div className="mt-6">
                <div className="h-2 bg-[var(--lavender)]">
                  <motion.div className="h-2 bg-[var(--ink)]"
                    initial={{ width: 0 }} animate={{ width: `${status?.progress_percent || 0}%` }}
                    transition={{ duration: 0.8 }} />
                </div>
                <p className="text-sm text-[var(--muted)] mt-3">{status?.progress_percent}% menuju Anggota Penuh</p>
              </div>
            </>
          ) : (
            <div className="border hairline p-5 sm:p-8 lav">
              <ShieldCheck size={36} />
              <p className="swiss-display text-2xl mt-4">Maturitas tercapai</p>
              <p className="text-[var(--muted)] mt-2">Anda kini dapat melengkapi verifikasi KYC.</p>
            </div>
          )}
        </div>

        {/* KYC Gate */}
        <div className="bg-white p-5 sm:p-8">
          <div className="flex items-center gap-2 mb-6">
            {matured ? <ShieldCheck size={18} /> : <Lock size={18} className="text-[var(--muted)]" />}
            <span className="mono-label">Verifikasi KYC</span>
            {kyc === "PENDING" && <Badge tone="lav">Menunggu Persetujuan</Badge>}
            {kyc === "APPROVED" && <Badge tone="ok">Anggota Penuh</Badge>}
          </div>

          {!matured && (
            <div data-testid="kyc-locked" className="border hairline border-dashed p-5 sm:p-8 text-center">
              <Lock size={28} className="mx-auto text-[var(--muted)]" />
              <p className="font-semibold mt-4">Fitur KYC Terkunci</p>
              <p className="text-sm text-[var(--muted)] mt-2">Tersedia setelah masa tunggu 365 hari selesai.</p>
            </div>
          )}

          {matured && kyc !== "APPROVED" && (
            <div data-testid="kyc-form" className="space-y-4">
              <div>
                <label className="mono-label">Nomor KTP (NIK)</label>
                <input data-testid="kyc-nik" className="field tap w-full px-4 mt-2" value={form.nik}
                  onChange={(e) => setForm({ ...form, nik: e.target.value })} disabled={kyc === "PENDING"} />
              </div>
              <div>
                <label className="mono-label">No. HP</label>
                <input data-testid="kyc-phone" className="field tap w-full px-4 mt-2" value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })} disabled={kyc === "PENDING"} />
              </div>
              <div>
                <label className="mono-label">Alamat</label>
                <textarea data-testid="kyc-address" rows={3} className="field w-full px-4 py-3 mt-2" value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })} disabled={kyc === "PENDING"} />
              </div>
              {msg && <p className="text-sm text-[var(--ink)]">{msg}</p>}
              <button data-testid="kyc-submit" onClick={submitKyc} disabled={kyc === "PENDING"}
                className="tap w-full btn-primary font-semibold disabled:opacity-40">
                {kyc === "PENDING" ? "Menunggu Persetujuan" : "Kirim Verifikasi"}
              </button>
            </div>
          )}

          {kyc === "APPROVED" && (
            <div className="border hairline p-5 sm:p-8 lav">
              <ShieldCheck size={32} className="text-[var(--ok)]" />
              <p className="font-semibold mt-3">Anda adalah Anggota Penuh koperasi.</p>
            </div>
          )}
        </div>
      </div>

      <section className="mt-10 border hairline bg-white p-5 sm:p-8">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 mb-3">
              <Fingerprint size={18} />
              <span className="mono-label">Keamanan Akun</span>
              {user?.biometric_enabled ? <Badge tone="ok">Biometric Aktif</Badge> : <Badge tone="lav">Opsional</Badge>}
            </div>
            <h2 className="font-bold text-xl">Biometric / Passkey</h2>
            <p className="text-sm text-[var(--muted)] mt-2">
              Aktifkan setelah masuk dengan Gmail atau PIN. Browser akan memakai passkey perangkat seperti Windows Hello, Face ID, Touch ID, atau kunci layar yang tersedia.
            </p>
            {user?.biometric_device_name && (
              <p className="text-sm mt-3">Perangkat aktif: <b>{user.biometric_device_name}</b></p>
            )}
            {bioMsg && <p className="text-sm text-[var(--ink)] mt-3">{bioMsg}</p>}
          </div>
          <div className="w-full lg:w-auto flex flex-col sm:flex-row gap-2">
            {user?.biometric_enabled ? (
              <button onClick={disableBiometric} disabled={bioBusy} className="tap btn-outline px-5 font-semibold disabled:opacity-50">
                Nonaktifkan
              </button>
            ) : (
              <button onClick={enableBiometric} disabled={bioBusy || !biometricSupported} className="tap btn-primary px-5 font-semibold disabled:opacity-50">
                {bioBusy ? "Memproses..." : "Aktifkan Biometric"}
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
