import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight, BarChart3, Boxes, ClipboardList, HandCoins,
  MessageSquareText, ShieldCheck,
} from "lucide-react";
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
        desc="Ringkasan aktivitas koperasi dan akses cepat ke 6 fungsi inti."
      />

      {!stats ? (
        <p className="mono-label">Memuat...</p>
      ) : (
        <>
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
                <Cell><div className="p-5 sm:p-6"><Link to="/transactions" className="mono-label flex items-center gap-1 hover:text-[var(--ink)]">Catat transaksi baru <ArrowUpRight size={13} /></Link></div></Cell>
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
          <ModuleGrid role={role} />
        </>
      )}
    </div>
  );
}

function ModuleGrid({ role }) {
  const modules = [
    { to: "/membership", label: "Keanggotaan", desc: "Profil digital, KYC, status anggota.", icon: ShieldCheck, roles: ["NELAYAN", "ADMIN"] },
    { to: "/savings-loans", label: "Simpan Pinjam", desc: "Simpanan, pengajuan pinjaman, cicilan.", icon: HandCoins, roles: ["NELAYAN", "ADMIN"] },
    { to: "/transactions", label: "Pencatatan POS", desc: "BBM, metode bayar, validasi nota.", icon: ClipboardList, roles: ["PETUGAS_LAPANG", "ADMIN"] },
    { to: "/inventory", label: "Inventori", desc: "Stok koperasi dan mutasi barang.", icon: Boxes, roles: ["PETUGAS_LAPANG", "ADMIN"] },
    { to: "/reports", label: "Laporan", desc: "Ringkasan kas dan export CSV.", icon: BarChart3, roles: ["ADMIN"] },
    { to: "/services", label: "Layanan", desc: "Tiket warga, anggota, dan pengumuman.", icon: MessageSquareText, roles: ["NELAYAN", "PETUGAS_LAPANG", "ADMIN"] },
  ].filter((m) => m.roles.includes(role));

  if (role === "PETUGAS_DINAS") {
    modules.push({ to: "/vessels", label: "Surat Rekomendasi", desc: "Data perahu dan kuota BBM.", icon: ShieldCheck, roles: ["PETUGAS_DINAS"] });
  }

  return (
    <div className="mt-10">
      <p className="mono-label mb-4">6 Fungsi Inti</p>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-px bg-[var(--line)] border hairline">
        {modules.map(({ to, label, desc, icon: Icon }) => (
          <Link key={to} to={to} className="bg-white p-5 sm:p-6 hover:bg-[var(--sky)] transition-colors min-h-[150px]">
            <div className="w-10 h-10 bg-[var(--sea)] text-white flex items-center justify-center"><Icon size={18} /></div>
            <p className="font-bold text-lg mt-5">{label}</p>
            <p className="text-sm text-[var(--muted)] mt-2">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

const Cell = ({ children }) => <div className="bg-white">{children}</div>;
