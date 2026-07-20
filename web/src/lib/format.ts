// Formatadores — espelham fmt_brl / fmt_pct / fmt_num do bq_client.py.

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function fmtBRL(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return brl.format(v);
}

export function fmtNum(v: number | null | undefined, decimals = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(v);
}

export function fmtPct(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(decimals)}%`;
}

// R$ X,XXM / R$ X.XXXk — usado nos rótulos de barra (igual ao _fmt_compact do Streamlit)
export function fmtCompact(v: number): string {
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(2).replace(".", ",")}M`;
  if (v >= 1_000) return `R$ ${Math.round(v / 1_000)}k`;
  return `R$ ${Math.round(v)}`;
}

// R$ X,XM / R$ Xk — versão curta dos cards RFV
export function fmtFat(v: number): string {
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (v >= 1_000) return `R$ ${Math.round(v / 1_000)}k`;
  return `R$ ${fmtNum(v)}`;
}

// Formatter de tooltip do Recharts (param largo p/ casar com o tipo ValueType).
export const tipBRL = (v: unknown): string => fmtBRL(Number(v));
