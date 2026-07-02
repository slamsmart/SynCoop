import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Home, ShieldCheck, Ship, Wallet, Calculator, Bell, FileCheck2,
  Fish, Users, Anchor, LogOut, X, ClipboardList, Gavel, Menu,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/lib/api";
import api from "@/lib/api";

const MENU = {
  NELAYAN: [
    { to: "/dashboard", label: "Beranda", icon: Home },
    { to: "/vessels", label: "Jatah Solar", icon: Ship },
    { to: "/debts", label: "Utang Saya", icon: Wallet },
    { to: "/fish-sales", label: "Jual Ikan", icon: Gavel },
    { to: "/calculator", label: "Hitung Ikan", icon: Calculator },
    { to: "/membership", label: "Kartu Anggota", icon: ShieldCheck },
    { to: "/notifications", label: "Kabar", icon: Bell },
  ],
  PETUGAS_LAPANG: [
    { to: "/dashboard", label: "Beranda", icon: Home },
    { to: "/transactions", label: "Catat BBM", icon: ClipboardList },
    { to: "/fish-sales", label: "Lelang Ikan", icon: Gavel },
    { to: "/vessels", label: "Data Perahu", icon: Ship },
    { to: "/debts", label: "Piutang", icon: Wallet },
  ],
  ADMIN: [
    { to: "/dashboard", label: "Beranda", icon: Home },
    { to: "/transactions", label: "Validasi", icon: FileCheck2 },
    { to: "/fish-sales", label: "Lelang Ikan", icon: Gavel },
    { to: "/debts", label: "Piutang", icon: Wallet },
    { to: "/vessels", label: "Data Perahu", icon: Ship },
    { to: "/fish-prices", label: "Harga Ikan", icon: Fish },
    { to: "/users", label: "Pengguna", icon: Users },
    { to: "/notifications", label: "Kabar", icon: Bell },
  ],
  PETUGAS_DINAS: [
    { to: "/dashboard", label: "Beranda", icon: Home },
    { to: "/vessels", label: "Rekomendasi", icon: FileCheck2 },
  ],
};

// items shown on the mobile bottom bar (max 4 + Menu)
const BOTTOM_COUNT = { NELAYAN: 4, PETUGAS_LAPANG: 4, ADMIN: 4, PETUGAS_DINAS: 2 };

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sheet, setSheet] = useState(false);
  const [unread, setUnread] = useState(0);

  const menu = MENU[user?.role] || MENU.NELAYAN;
  const bottomItems = menu.slice(0, BOTTOM_COUNT[user?.role] || 4);
  const extraItems = menu.slice(BOTTOM_COUNT[user?.role] || 4);

  useEffect(() => { setSheet(false); }, [location.pathname]);

  useEffect(() => {
    api.get("/notifications").then((r) => setUnread(r.data.unread)).catch(() => {});
  }, [location.pathname]);

  if (!user) return null;

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Mobile top bar */}
      <div className="lg:hidden flex items-center justify-between px-4 h-16 border-b hairline sticky top-0 bg-white z-40">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 bg-[var(--ink)] text-white flex items-center justify-center"><Anchor size={17} /></div>
          <div>
            <div className="font-extrabold tracking-tight leading-none text-[15px]">SynCoop</div>
            <div className="mono-label !text-[10px]">{ROLE_LABELS[user.role]}</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <NavLink to="/notifications" data-testid="topbar-bell" className="relative w-11 h-11 flex items-center justify-center">
            <Bell size={22} />
            {unread > 0 && (
              <span className="absolute top-1 right-1 min-w-[18px] h-[18px] text-[10px] font-bold bg-[var(--danger)] text-white rounded-full flex items-center justify-center px-1">{unread}</span>
            )}
          </NavLink>
          <button data-testid="logout-btn-mobile" onClick={logout} className="w-11 h-11 flex items-center justify-center text-[var(--muted)]">
            <LogOut size={20} />
          </button>
        </div>
      </div>

      {/* Desktop sidebar */}
      <aside className="hidden lg:flex lg:w-72 lg:shrink-0 border-r hairline bg-white lg:sticky lg:top-0 lg:h-screen flex-col">
        <div className="flex items-center gap-3 px-6 h-20 border-b hairline">
          <div className="w-9 h-9 bg-[var(--ink)] text-white flex items-center justify-center"><Anchor size={18} /></div>
          <div>
            <div className="font-extrabold tracking-tight leading-none">SynCoop</div>
            <div className="mono-label">Koperasi Digital</div>
          </div>
        </div>

        <nav className="px-3 py-5 space-y-1 flex-1">
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

        <div className="px-3 pb-5">
          <div className="border hairline p-3 mb-2">
            <div className="text-[13px] font-semibold truncate">{user.name}</div>
            <div className="mono-label truncate">{ROLE_LABELS[user.role]}</div>
          </div>
          <button
            data-testid="logout-btn"
            onClick={logout}
            className="flex items-center gap-2 px-3 h-10 w-full text-[13px] font-medium text-[var(--muted)] hover:text-[var(--danger)] transition-colors"
          >
            <LogOut size={16} /> Keluar
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0 px-4 sm:px-6 lg:px-12 py-6 lg:py-12 pb-28 lg:pb-12">
        <Outlet />
      </main>

      {/* Mobile bottom navigation */}
      <nav data-testid="bottom-nav" className="lg:hidden fixed bottom-0 inset-x-0 z-50 bg-white border-t hairline bottom-nav">
        <div className="flex">
          {bottomItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/dashboard"}
              data-testid={`bottomnav-${to.replace("/", "")}`}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center justify-center gap-1 pt-2.5 pb-2 ${
                  isActive ? "text-[var(--ink)] bnav-active" : "text-[var(--muted)]"
                }`
              }
            >
              <Icon size={23} strokeWidth={2.2} />
              <span className="text-[10.5px] font-semibold leading-none">{label}</span>
            </NavLink>
          ))}
          {extraItems.length > 0 && (
            <button
              data-testid="bottomnav-more"
              onClick={() => setSheet(true)}
              className="flex-1 flex flex-col items-center justify-center gap-1 pt-2.5 pb-2 text-[var(--muted)]"
            >
              <Menu size={23} strokeWidth={2.2} />
              <span className="text-[10.5px] font-semibold leading-none">Lainnya</span>
            </button>
          )}
        </div>
      </nav>

      {/* Mobile "more" sheet */}
      {sheet && (
        <div className="lg:hidden fixed inset-0 z-[60]" data-testid="more-sheet">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSheet(false)} />
          <div className="absolute bottom-0 inset-x-0 bg-white border-t hairline p-5 pb-8 sheet-up">
            <div className="flex items-center justify-between mb-4">
              <p className="mono-label">Menu Lainnya</p>
              <button onClick={() => setSheet(false)} className="w-10 h-10 flex items-center justify-center"><X size={20} /></button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {extraItems.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  data-testid={`sheet-${to.replace("/", "")}`}
                  className="flex flex-col items-center gap-2 border hairline py-5 hover:bg-[var(--lavender)]"
                >
                  <Icon size={24} />
                  <span className="text-[12px] font-semibold text-center leading-tight px-1">{label}</span>
                  {to === "/notifications" && unread > 0 && (
                    <span className="text-[10px] font-bold bg-[var(--danger)] text-white px-1.5 rounded-full">{unread}</span>
                  )}
                </NavLink>
              ))}
              <button onClick={logout} className="flex flex-col items-center gap-2 border hairline py-5 text-[var(--danger)]">
                <LogOut size={24} />
                <span className="text-[12px] font-semibold">Keluar</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
