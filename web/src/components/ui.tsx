import { useMemo, useState, type ReactNode } from "react";
import { VARIANT_BORDER, type Variant } from "../theme";

// ── KPI card ──────────────────────────────────────────────────
export function KpiCard({
  label, value, delta, deltaDir = "flat", variant = "",
}: {
  label: ReactNode; value: ReactNode; delta?: ReactNode;
  deltaDir?: "up" | "down" | "flat"; variant?: Variant;
}) {
  const arrow = deltaDir === "up" ? "▲" : deltaDir === "down" ? "▼" : "•";
  const pillBg =
    deltaDir === "up"
      ? "bg-emerald-50 text-emerald-700"
      : deltaDir === "down"
      ? "bg-red-50 text-red-700"
      : "bg-gray-100 text-gray-600";
  return (
    <div
      className="bg-white rounded-xl px-5 py-5 h-full min-h-[120px]"
      style={{
        borderLeft: `3px solid ${VARIANT_BORDER[variant]}`,
        boxShadow: "0 1px 2px rgba(20,15,80,0.03)",
      }}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 m-0">{label}</p>
      <p className="text-[24px] font-bold text-gray-900 leading-tight m-0 mt-1.5 break-words">{value}</p>
      {delta != null && delta !== "" && (
        <div className="mt-2">
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${pillBg}`}
          >
            <span>{arrow}</span> {delta}
          </span>
        </div>
      )}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <p
      className="text-[15px] mt-10 mb-3 tracking-wide"
      style={{ color: "#15151F", fontWeight: 600 }}
    >
      {children}
    </p>
  );
}

export function Caption({ children }: { children: ReactNode }) {
  return <p className="text-[12px] text-gray-500 leading-relaxed mb-2">{children}</p>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`bg-white rounded-xl p-5 border border-[#F0F0F8]/70 ${className}`}
      style={{
        boxShadow:
          "0 1px 2px rgba(20,15,80,0.04), 0 4px 16px rgba(20,15,80,0.03)",
      }}
    >
      {children}
    </div>
  );
}

export function ChartTitle({ children }: { children: ReactNode }) {
  return (
    <p className="text-[13px] font-semibold text-gray-600 tracking-wide mb-3">{children}</p>
  );
}

// ── Select estilizado ─────────────────────────────────────────
export function Select({
  label, value, onChange, options,
}: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800
                   focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882] cursor-pointer"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

// ── Tabela genérica ───────────────────────────────────────────
export interface Column<T> {
  key: keyof T | string;
  header: string;
  align?: "left" | "right" | "center";
  render?: (row: T) => ReactNode;
  // Valor usado pra ordenar (números ordenam numérico; ex.: data -> use dias). Se
  // ausente, ordena pelo valor bruto de row[key].
  sortAccessor?: (row: T) => number | string;
}

export function DataTable<T>({ columns, rows, sortable }: { columns: Column<T>[]; rows: T[]; sortable?: boolean }) {
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);

  const sortedRows = useMemo(() => {
    if (!sortable || !sort) return rows;
    const col = columns.find((c) => String(c.key) === sort.key);
    if (!col) return rows;
    const val = (r: T) => col.sortAccessor
      ? col.sortAccessor(r)
      : ((r as Record<string, unknown>)[col.key as string] as number | string);
    const arr = [...rows].sort((a, b) => {
      const va = val(a), vb = val(b);
      if (typeof va === "number" && typeof vb === "number") return va - vb;
      return String(va).localeCompare(String(vb), "pt-BR", { numeric: true });
    });
    return sort.dir === "desc" ? arr.reverse() : arr;
  }, [rows, sort, sortable, columns]);

  const onHeader = (key: string) => {
    if (!sortable) return;
    setSort((s) => s?.key === key
      ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
      : { key, dir: "desc" });
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-[#F8F9FE]">
            {columns.map((c) => {
              const active = sort?.key === String(c.key);
              return (
              <th
                key={String(c.key)}
                onClick={() => onHeader(String(c.key))}
                className={`px-3 py-3.5 font-medium text-[10.5px] uppercase tracking-[0.12em] whitespace-nowrap
                  ${active ? "text-[#1E1882]" : "text-gray-500"} ${sortable ? "cursor-pointer select-none hover:text-[#1E1882]" : ""}
                  ${c.align === "right" ? "text-right" : c.align === "center" ? "text-center" : "text-left"}`}
              >
                {c.header}{sortable && (active ? (sort!.dir === "desc" ? " ↓" : " ↑") : " ⇅")}
              </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, i) => (
            <tr key={i} className="border-b border-[#F5F5FA] hover:bg-[#FAFAFE]">
              {columns.map((c) => (
                <td
                  key={String(c.key)}
                  className={`px-3 py-3.5 text-gray-700
                    ${c.align === "right" ? "text-right tabular-nums" : c.align === "center" ? "text-center" : "text-left"}`}
                >
                  {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key as string] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Estados auxiliares ────────────────────────────────────────
export function Spinner({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-gray-500 text-sm py-10 justify-center">
      <span className="h-4 w-4 rounded-full border-2 border-[#1E1882] border-t-transparent animate-spin" />
      {label}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg bg-[#FDF5F5] border-l-4 border-[#DC2626] text-red-700 p-4 text-sm">
      {message}
    </div>
  );
}

export function InfoBox({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg bg-[#F5F7FF] border-l-4 border-[#4844C8] text-[#1E1882] p-4 text-sm">
      {children}
    </div>
  );
}
