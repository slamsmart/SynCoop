import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import api, { fmtRp, ROLE_LABELS } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard } from "@/components/ui-kit";

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
  }, []);

  const role = user?.role;

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
          {role === "NELAYAN" && (
            <>
              <Cell><StatCard index={0} label="Perahu Terdaftar" value={stats.vessel_count} /></Cell>
              <Cell><StatCard index={1} label="Sisa Kuota BBM" value={`${stats.quota_remaining} L`} sub={`Terpakai ${stats.quota_used} L dari ${stats.quota_total} L`} /></Cell>
              <Cell><StatCard index={2} label="Total Utang" value={fmtRp(stats.outstanding_debt)} danger={stats.outstanding_debt > 0} /></Cell>
              <Cell><StatCard index={3} label="Tagihan Aktif" value={stats.debt_count} /></Cell>
            </>
          )}
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

const Cell = ({ children }) => <div className="bg-white">{children}</div>;
