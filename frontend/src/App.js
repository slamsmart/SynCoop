import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Membership from "@/pages/Membership";
import Vessels from "@/pages/Vessels";
import Transactions from "@/pages/Transactions";
import Debts from "@/pages/Debts";
import Calculator from "@/pages/Calculator";
import FishSales from "@/pages/FishSales";
import FishPrices from "@/pages/FishPrices";
import Users from "@/pages/Users";
import Notifications from "@/pages/Notifications";
import SavingsLoans from "@/pages/SavingsLoans";
import Inventory from "@/pages/Inventory";
import Reports from "@/pages/Reports";
import Services from "@/pages/Services";
import PublicPortal from "@/pages/PublicPortal";
import PageSettings from "@/pages/PageSettings";
import FingerprintReporter from "@/components/FingerprintReporter";
import useScrollReveal from "@/hooks/useScrollReveal";

function Protected({ children }) {
  const { user, loading, loggingOut } = useAuth();
  if (loggingOut) return <div className="min-h-screen bg-white" />;
  if (loading) return <div className="min-h-screen flex items-center justify-center"><p className="mono-label">Memuat…</p></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RoleRoute({ roles, children }) {
  const { user } = useAuth();
  if (user && !roles.includes(user.role)) return <Navigate to="/dashboard" replace />;
  return children;
}

function AppRouter() {
  useScrollReveal();

  return (
    <Routes>
      <Route path="/" element={<PublicPortal />} />
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/membership" element={<RoleRoute roles={["NELAYAN", "ADMIN"]}><Membership /></RoleRoute>} />
        <Route path="/savings-loans" element={<RoleRoute roles={["NELAYAN", "ADMIN"]}><SavingsLoans /></RoleRoute>} />
        <Route path="/vessels" element={<Vessels />} />
        <Route path="/transactions" element={<RoleRoute roles={["PETUGAS_LAPANG", "ADMIN"]}><Transactions /></RoleRoute>} />
        <Route path="/debts" element={<Debts />} />
        <Route path="/calculator" element={<RoleRoute roles={["NELAYAN"]}><Calculator /></RoleRoute>} />
        <Route path="/fish-sales" element={<FishSales />} />
        <Route path="/inventory" element={<RoleRoute roles={["ADMIN", "PETUGAS_LAPANG"]}><Inventory /></RoleRoute>} />
        <Route path="/reports" element={<RoleRoute roles={["ADMIN"]}><Reports /></RoleRoute>} />
        <Route path="/services" element={<Services />} />
        <Route path="/fish-prices" element={<RoleRoute roles={["ADMIN"]}><FishPrices /></RoleRoute>} />
        <Route path="/page-settings" element={<RoleRoute roles={["ADMIN"]}><PageSettings /></RoleRoute>} />
        <Route path="/users" element={<RoleRoute roles={["ADMIN"]}><Users /></RoleRoute>} />
        <Route path="/notifications" element={<Notifications />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <FingerprintReporter />
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
