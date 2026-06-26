import { useEffect, useState, useCallback } from "react";
import { CheckCircle2 } from "lucide-react";
import api, { ROLE_LABELS } from "@/lib/api";
import { PageHeader, Badge, Empty } from "@/components/ui-kit";

const ROLES = ["NELAYAN", "PETUGAS_LAPANG", "ADMIN", "PETUGAS_DINAS"];

export default function Users() {
  const [users, setUsers] = useState([]);
  const load = useCallback(() => {
    api.get("/admin/users").then((r) => setUsers(r.data)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const setRole = async (id, role) => { await api.put(`/admin/users/${id}/role`, { role }); load(); };
  const approveKyc = async (id) => { await api.post(`/admin/kyc/${id}/approve`); load(); };

  return (
    <div data-testid="users-page">
      <PageHeader kicker="Administrasi" title="Manajemen Pengguna"
        desc="Atur peran pengguna dan setujui verifikasi KYC anggota." />
      {users.length === 0 ? <Empty>Belum ada pengguna.</Empty> : (
        <div className="border hairline divide-y divide-[var(--line)]">
          {users.map((u) => (
            <div key={u.user_id} data-testid="user-row" className="p-5 flex flex-col md:flex-row md:items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold truncate">{u.name}</span>
                  {u.kyc_status === "PENDING" && <Badge tone="lav">KYC Pending</Badge>}
                  {u.is_kyc_approved && <Badge tone="ok">Anggota Penuh</Badge>}
                </div>
                <p className="mono-label mt-1 truncate">{u.email}</p>
              </div>
              <div className="flex items-center gap-2">
                <select data-testid="user-role-select" value={u.role} onChange={(e) => setRole(u.user_id, e.target.value)}
                  className="field px-3 py-2 text-sm">
                  {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                </select>
                {u.kyc_status === "PENDING" && (
                  <button data-testid="approve-kyc-btn" onClick={() => approveKyc(u.user_id)}
                    className="btn-outline px-3 py-2 text-sm font-semibold flex items-center gap-1"><CheckCircle2 size={14} /> Setujui KYC</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
