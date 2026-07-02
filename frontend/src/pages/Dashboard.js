import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Ship, Wallet, Calculator, Gavel, Fuel, Fish, ShieldCheck, ChevronRight } from "lucide-react";
import api, { fmtRp, ROLE_LABELS } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard } from "@/components/ui-kit";

const todayStr = () =>
  new Date().toLocaleDateString("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
  }, []);

  const role = user?.role;

  if (role === "NELAYAN") return <NelayanHome user={user} stats={stats} />;

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        kicker={ROLE_LABELS[role]}
        title={`Halo, ${user?.name?.split(" ")[0]}.`}
        desc="Ringkasan aktivitas koperasi Anda hari ini."
      />

      {!stats ? (
        <p className="mono-label">Memuat…</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-px bg-[var(--line)] border hairline">
          {role === "PETUGAS_DINAS" && (
            <>
              <Cell><StatCard index={0} label="Total Perahu" value={stats.total_vessels} /></Cell>
              <Cell><StatCard index={1} label="Pas Besar" value={stats.pas_besar} /></Cell>
              <Cell><StatCard index={2} label="Pas Kecil" value={stats.pas_kecil} /></Cell>
              <Cell><StatCard index={3} label="Nelayan" value={stats.total_fishermen} /></Cell>
            </>
          )}
          {role === "PETUGAS_LAPANG" && (
            <>
              <Cell><StatCard index={0} label="Transaksi Bulan Ini" value={stats.transactions_this_month} /></Cell>
              <Cell><StatCard index={1} label="Liter Terdistribusi" value={`${stats.liters_this_month} L`} /></Cell>
              <Cell><StatCard index={2} label="Menunggu Validasi" value={stats.pending_validation} /></Cell>
              <Cell><div className="p-6"><Link to="/transactions" className="mono-label flex items-center gap-1 hover:text-[var(--ink)]">Catat transaksi baru <ArrowUpRight size={13} /></Link></div></Cell>
            </>
          )}
          {role === "ADMIN" && (
            <>
              <Cell><StatCard index={0} label="Total Piutang" value={fmtRp(stats.total_outstanding)} danger={stats.total_outstanding > 0} sub={`${stats.debtor_count} penunggak`} /></Cell>
              <Cell><StatCard index={1} label="Menunggu Validasi" value={stats.pending_validation + (stats.pending_sale_validation || 0)} sub={`${stats.pending_validation} BBM · ${stats.pending_sale_validation || 0} Lelang`} /></Cell>
              <Cell><StatCard index={2} label="KYC Pending" value={stats.pending_kyc} /></Cell>
              <Cell><StatCard index={3} label="Total Pengguna" value={stats.total_users} sub={`${stats.total_vessels} perahu · ${stats.total_transactions} transaksi`} /></Cell>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------- Beranda Nelayan ------------------------- */
function NelayanHome({ user, stats }) {
  const [prices, setPrices] = useState([]);

  useEffect(() => {
    api.get("/fish-prices").then((r) => setPrices(r.data)).catch(() => {});
  }, []);

  const quotaPct = stats && stats.quota_total > 0
    ? Math.min(100, Math.round((stats.quota_remaining / stats.quota_total) * 100))
    : 0;
  const gaugeColor = quotaPct > 50 ? "var(--ok)" : quotaPct > 20 ? "#B45309" : "var(--danger)";

  const daysLeft = user?.maturation_end_date
    ? Math.max(0, Math.ceil((new Date(user.maturation_end_date) - new Date()) / 86400000))
    : 0;
  const isAnggota = user?.is_kyc_approved;

  return (
    <div data-testid="dashboard-page" className="max-w-2xl mx-auto lg:mx-0">
      <div className="mb-6 fade-up">
        <p className="mono-label mb-1">{todayStr()}</p>
        <h1 className="swiss-display text-3xl sm:text-4xl">Halo, {user?.name?.split(" ")[0]}.</h1>
      </div>

      {/* Membership status banner */}
      {!isAnggota && (
        <Link to="/membership" data-testid="membership-banner"
          className="flex items-center gap-3 lav p-4 mb-4 border hairline">
          <ShieldCheck size={22} className="shrink-0" />
          <div className="flex-1">
            <p className="text-[14px] font-semibold leading-tight">
              {user?.kyc_status === "PENDING" ? "Berkas Anda sedang diperiksa koperasi"
                : daysLeft > 0 ? `${daysLeft} hari lagi jadi Anggota Penuh`
                : "Lengkapi berkas untuk jadi Anggota Penuh"}
            </p>
            <p className="text-[12px] text-[var(--muted)]">Ketuk untuk lihat kartu anggota</p>
          </div>
          <ChevronRight size={18} className="text-[var(--muted)]" />
        </Link>
      )}

      {!stats ? (
        <p className="mono-label">Memuat…</p>
      ) : (
        <div className="space-y-4">
          {/* Jatah Solar */}
          <Link to="/vessels" data-testid="home-quota-card" className="block border hairline p-5 bg-white hover:bg-[var(--lavender)] transition-colors">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-11 h-11 bg-[var(--ink)] text-white flex items-center justify-center"><Fuel size={22} /></div>
              <div className="flex-1">
                <p className="mono-label">Jatah Solar Bulan Ini</p>
                <p className="swiss-display text-3xl mt-0.5">
                  {stats.quota_remaining} <span className="text-lg font-bold">Liter tersisa</span>
                </p>
              </div>
              <ChevronRight size={18} className="text-[var(--muted)]" />
            </div>
            <div className="h-3 bg-[var(--line)] overflow-hidden">
              <div className="h-full transition-all" style={{ width: `${quotaPct}%`, background: gaugeColor }} />
            </div>
            <p className="text-[13px] text-[var(--muted)] mt-2">
              Sudah dipakai {stats.quota_used} L dari jatah {stats.quota_total} L · {stats.vessel_count} perahu
            </p>
          </Link>

          {/* Utang */}
          <Link to="/debts" data-testid="home-debt-card" className="block border hairline p-5 bg-white hover:bg-[var(--lavender)] transition-colors">
            <div className="flex items-center gap-3">
              <div className={`w-11 h-11 flex items-center justify-center text-white ${stats.outstanding_debt > 0 ? "bg-[var(--danger)]" : "bg-[var(--ok)]"}`}>
                <Wallet size={22} />
              </div>
              <div className="flex-1">
                <p className="mono-label">Utang Saya</p>
                {stats.outstanding_debt > 0 ? (
                  <>
                    <p className="swiss-display text-3xl mt-0.5 text-[var(--danger)]">{fmtRp(stats.outstanding_debt)}</p>
                    <p className="text-[13px] text-[var(--muted)] mt-1">{stats.debt_count} tagihan belum lunas · ketuk untuk lihat</p>
                  </>
                ) : (
                  <p className="swiss-display text-2xl mt-0.5 text-[var(--ok)]">Lunas, tidak ada utang 🎉</p>
                )}
              </div>
              <ChevronRight size={18} className="text-[var(--muted)]" />
            </div>
          </Link>

          {/* Harga ikan hari ini */}
          <div className="border hairline bg-white" data-testid="home-fish-prices">
            <div className="flex items-center gap-2 p-4 pb-2">
              <Fish size={18} />
              <p className="mono-label !text-[var(--ink)]">Harga Ikan Hari Ini</p>
            </div>
            {prices.length === 0 ? (
              <p className="px-4 pb-4 text-sm text-[var(--muted)]">Belum ada harga ikan.</p>
            ) : (
              <div className="divide-y divide-[var(--line)]">
                {prices.slice(0, 5).map((f) => (
                  <div key={f.fish_id} className="flex items-center justify-between px-4 py-3">
                    <span className="font-semibold text-[15px]">{f.name}</span>
                    <span className="tabular-nums font-bold text-[15px]">{fmtRp(f.price_per_kg)}<span className="text-[var(--muted)] font-medium text-[12px]">/kg</span></span>
                  </div>
                ))}
              </div>
            )}
            <Link to="/calculator" data-testid="home-calc-link"
              className="flex items-center justify-center gap-2 border-t hairline py-3.5 font-semibold text-[14px] hover:bg-[var(--lavender)] transition-colors">
              <Calculator size={17} /> Hitung Hasil Tangkapan <ArrowUpRight size={14} />
            </Link>
          </div>

          {/* Quick actions */}
          <div className="grid grid-cols-2 gap-2">
            <QuickBtn to="/fish-sales" icon={Gavel} label="Penjualan Ikan Saya" testId="quick-sales" />
            <QuickBtn to="/vessels" icon={Ship} label="Perahu Saya" testId="quick-vessels" />
          </div>
        </div>
      )}
    </div>
  );
}

const QuickBtn = ({ to, icon: Icon, label, testId }) => (
  <Link to={to} data-testid={testId}
    className="flex flex-col items-start gap-3 border hairline bg-white p-4 min-h-[92px] hover:bg-[var(--lavender)] transition-colors">
    <Icon size={22} />
    <span className="font-semibold text-[14px] leading-tight">{label}</span>
  </Link>
);

const Cell = ({ children }) => <div className="bg-white">{children}</div>;
