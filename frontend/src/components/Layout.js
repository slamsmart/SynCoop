import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  LayoutGrid, ShieldCheck, Ship, Wallet, Calculator, Bell, FileCheck2,
  Fish, Users, Anchor, LogOut, Menu, X, ClipboardList, Gavel,
  HandCoins, Boxes, BarChart3, MessageSquareText, Settings,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/api";
import api from "@/lib/api";

const MENU = {
  NELAYAN: [
    { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
    { to: "/membership", label: "Keanggotaan", icon: ShieldCheck },
    { to: "/savings-loans", label: "Simpan Pinjam", icon: HandCoins },
    { to: "/vessels", label: "Perahu & Kuota", icon: Ship },
    { to: "/debts", label: "Utang Saya", icon: Wallet },
    { to: "/fish-sales", label: "Penjualan Ikan", icon: Gavel },
    { to: "/calculator", label: "Kalkulator Ikan", icon: Calculator },
    { to: "/services", label: "Layanan", icon: MessageSquareText },
    { to: "/notifications", label: "Notifikasi", icon: Bell },
  ],
  PETUGAS_LAPANG: [
    { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
    { to: "/transactions", label: "Catat Transaksi", icon: ClipboardList },
    { to: "/fish-sales", label: "Lelang Ikan", icon: Gavel },
    { to: "/inventory", label: "Inventori", icon: Boxes },
    { to: "/services", label: "Layanan", icon: MessageSquareText },
    { to: "/vessels", label: "Data Perahu", icon: Ship },
    { to: "/debts", label: "Master Piutang", icon: Wallet },
  ],
  ADMIN: [
    { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
    { to: "/membership", label: "Keanggotaan", icon: ShieldCheck },
    { to: "/savings-loans", label: "Simpan Pinjam", icon: HandCoins },
    { to: "/transactions", label: "Validasi Transaksi", icon: FileCheck2 },
    { to: "/fish-sales", label: "Lelang Ikan", icon: Gavel },
    { to: "/inventory", label: "Inventori", icon: Boxes },
    { to: "/reports", label: "Laporan", icon: BarChart3 },
    { to: "/services", label: "Layanan", icon: MessageSquareText },
    { to: "/debts", label: "Master Piutang", icon: Wallet },
    { to: "/vessels", label: "Data Perahu", icon: Ship },
    { to: "/fish-prices", label: "Harga Ikan & Bagi Hasil", icon: Fish },
    { to: "/page-settings", label: "Pengaturan Halaman", icon: Settings },
    { to: "/users", label: "Manajemen Pengguna", icon: Users },
    { to: "/notifications", label: "Notifikasi", icon: Bell },
  ],
  PETUGAS_DINAS: [
    { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
    { to: "/vessels", label: "Surat Rekomendasi", icon: FileCheck2 },
  ],
};

export default function Layout() {
  const { user, logout, loggingOut } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);

  const menu = MENU[user?.role] || MENU.NELAYAN;

  useEffect(() => { setOpen(false); }, [location.pathname]);

  useEffect(() => {
    api.get("/notifications").then((r) => setUnread(r.data.unread)).catch(() => {});
  }, [location.pathname]);

  if (!user) return null;

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Mobile top bar */}
      <div className="lg:hidden flex items-center justify-between px-4 h-16 border-b hairline sticky top-0 bg-white z-40">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 bg-[var(--ink)] text-white flex items-center justify-center"><Anchor size={16} /></div>
          <span className="mono-label !text-[var(--ink)]">SynCoop</span>
        </Link>
        <button data-testid="mobile-menu-toggle" onClick={() => setOpen(!open)} className="tap w-10 flex items-center justify-center">
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Sidebar */}
      <aside className={`${open ? "flex" : "hidden"} lg:flex lg:w-72 lg:shrink-0 border-r hairline bg-white lg:sticky lg:top-0 lg:h-screen max-h-[calc(100vh-4rem)] lg:max-h-screen flex-col overflow-hidden`}>
        <Link to="/" className="hidden lg:flex items-center gap-3 px-6 h-20 border-b hairline hover:bg-[var(--lavender)] transition-colors">
          <div className="w-9 h-9 bg-[var(--ink)] text-white flex items-center justify-center"><Anchor size={18} /></div>
          <div>
            <div className="font-extrabold tracking-tight leading-none">SynCoop</div>
            <div className="mono-label">Koperasi Digital</div>
          </div>
        </Link>

        <nav className="px-3 py-5 flex-1 min-h-0 overflow-y-auto flex flex-col gap-1">
          <p className="mono-label px-3 pb-2">Menu</p>
          {menu.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/dashboard"}
              data-testid={`nav-${to.replace("/", "")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 h-11 text-[14px] font-medium transition-colors ${
                  isActive ? "bg-[var(--ink)] text-white" : "text-[var(--ink)] hover:bg-[var(--lavender)]"
                }`
              }
            >
              <Icon size={17} />
              <span className="flex-1">{label}</span>
              {to === "/notifications" && unread > 0 && (
                <span className="text-[10px] font-bold bg-[var(--danger)] text-white px-1.5 rounded-full">{unread}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 pt-3 pb-5 border-t hairline shrink-0 bg-white">
          <div className="border hairline p-3 mb-2">
            <div className="text-[13px] font-semibold truncate">{user.name}</div>
            <div className="mono-label truncate">{ROLE_LABELS[user.role]}</div>
          </div>
          <button
            data-testid="logout-btn"
            onClick={logout}
            disabled={loggingOut}
            className="flex items-center gap-2 px-3 h-10 w-full text-[13px] font-medium text-[var(--muted)] hover:text-[var(--danger)] transition-colors disabled:opacity-50"
          >
            <LogOut size={16} /> {loggingOut ? "Keluar..." : "Keluar"}
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0 w-full px-4 sm:px-6 lg:px-12 py-6 sm:py-8 lg:py-12">
        <Outlet />
      </main>
    </div>
  );
}
