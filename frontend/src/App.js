import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import AuthCallback from "@/pages/AuthCallback";
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

function Protected({ children }) {
  const { user, loading } = useAuth();
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
  const location = useLocation();
  // Handle OAuth callback synchronously before any auth check
  if (location.hash?.includes("session_id=")) return <AuthCallback />;

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/membership" element={<RoleRoute roles={["NELAYAN"]}><Membership /></RoleRoute>} />
        <Route path="/vessels" element={<Vessels />} />
        <Route path="/transactions" element={<RoleRoute roles={["PETUGAS_LAPANG", "ADMIN"]}><Transactions /></RoleRoute>} />
        <Route path="/debts" element={<Debts />} />
        <Route path="/calculator" element={<RoleRoute roles={["NELAYAN"]}><Calculator /></RoleRoute>} />
        <Route path="/fish-sales" element={<FishSales />} />
        <Route path="/fish-prices" element={<RoleRoute roles={["ADMIN"]}><FishPrices /></RoleRoute>} />
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
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
