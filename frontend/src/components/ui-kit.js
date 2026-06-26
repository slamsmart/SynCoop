import { motion } from "framer-motion";

export function PageHeader({ kicker, title, desc, action }) {
  return (
    <div className="flex items-end justify-between gap-4 mb-10 fade-up">
      <div>
        {kicker && <p className="mono-label mb-3">{kicker}</p>}
        <h1 className="swiss-display text-4xl sm:text-5xl">{title}</h1>
        {desc && <p className="text-[var(--muted)] mt-3 max-w-xl">{desc}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatCard({ label, value, sub, danger, index = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06 }}
      className="border hairline p-6"
    >
      <p className="mono-label">{label}</p>
      <p className={`swiss-display text-4xl mt-3 ${danger ? "text-[var(--danger)]" : ""}`}>{value}</p>
      {sub && <p className="text-sm text-[var(--muted)] mt-2">{sub}</p>}
    </motion.div>
  );
}

export function Badge({ children, tone = "ink" }) {
  const tones = {
    ink: "bg-[var(--ink)] text-white",
    lav: "bg-[var(--lavender)] text-[var(--ink)]",
    danger: "bg-[var(--danger)] text-white",
    ok: "bg-[var(--ok)] text-white",
    outline: "border border-[var(--line)] text-[var(--muted)]",
  };
  return <span className={`inline-block text-[11px] font-semibold tracking-wide px-2 py-1 ${tones[tone]}`}>{children}</span>;
}

export function Empty({ children }) {
  return <div className="border hairline border-dashed p-10 text-center text-[var(--muted)] text-sm">{children}</div>;
}
