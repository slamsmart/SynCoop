import { useEffect, useState, useCallback } from "react";
import { Bell, AlertCircle, Info } from "lucide-react";
import api from "@/lib/api";
import { PageHeader, Empty } from "@/components/ui-kit";

export default function Notifications() {
  const [items, setItems] = useState([]);
  const load = useCallback(() => {
    api.get("/notifications").then((r) => setItems(r.data.items)).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);

  const read = async (id) => { await api.post(`/notifications/${id}/read`); load(); };

  const icon = (t) => t === "REMINDER" || t === "DEBT" ? <AlertCircle size={18} className="text-[var(--danger)]" /> : <Info size={18} />;

  return (
    <div data-testid="notifications-page">
      <PageHeader kicker="Loop Notifikasi" title="Notifikasi" desc="Pengingat tagihan dan info dari koperasi." />
      {items.length === 0 ? <Empty>Tidak ada notifikasi.</Empty> : (
        <div className="border hairline divide-y divide-[var(--line)]">
          {items.map((n) => (
            <button key={n.notif_id} data-testid="notif-row" onClick={() => !n.is_read && read(n.notif_id)}
              className={`w-full text-left p-5 flex items-start gap-3 transition-colors ${n.is_read ? "opacity-60" : "hover:bg-[var(--lavender)]"}`}>
              {icon(n.type)}
              <div className="flex-1">
                <p className="text-sm">{n.message}</p>
                <p className="mono-label mt-1">{new Date(n.created_at).toLocaleString("id-ID")}</p>
              </div>
              {!n.is_read && <span className="w-2 h-2 bg-[var(--danger)] rounded-full mt-1" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
