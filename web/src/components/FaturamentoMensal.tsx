import type { ReactElement } from "react";
import { useFaturamentoAnual, type FatYear } from "../lib/api";
import { Card, ChartTitle, Spinner, ErrorBox, InfoBox } from "./ui";

// R$ com ponto de milhar, sem decimais
const brl0 = (v: number) => "R$ " + Math.round(v).toLocaleString("pt-BR");
const brlBare = (v: number) => brl0(v).replace("R$ ", "");

// Cor de fundo/texto pelo crescimento vs o ano anterior.
function corYoY(pct: number | null): { bg: string; fg: string } {
  if (pct == null) return { bg: "#F7F7FB", fg: "#15151F" };
  if (pct >= 0.3) return { bg: "#10B981", fg: "#FFFFFF" };
  if (pct >= 0) return { bg: "#FDE68A", fg: "#8A5A00" };
  return { bg: "#FCA5A5", fg: "#7F1D1D" };
}

const pctTxt = (pct: number) => Math.round(pct * 100) + "%";

// Estilos base de célula
const TD = "px-2 py-1 text-right tabular-nums whitespace-nowrap";
const LABEL = "px-2 py-1 text-left whitespace-nowrap";
const DARK_BG = "#2C2C3A";

export default function FaturamentoMensal() {
  const { data, isLoading, error } = useFaturamentoAnual();

  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox message={(error as Error).message} />;
  if (!data || data.years.length === 0)
    return <InfoBox>Sem dados de faturamento anual disponíveis.</InfoBox>;

  const { months, years } = data;

  return (
    <Card>
      <ChartTitle>Faturamento Mensal — 3 anos (YoY)</ChartTitle>
      <div className="overflow-x-auto">
        <table className="border-collapse text-[11px]" style={{ minWidth: "100%" }}>
          <thead>
            <tr>
              <th
                className="px-2 py-1.5 text-left font-semibold whitespace-nowrap"
                style={{ background: DARK_BG, color: "#FFFFFF" }}
              />
              {months.map((m) => (
                <th
                  key={m}
                  className="px-2 py-1.5 text-right font-semibold whitespace-nowrap"
                  style={{ background: DARK_BG, color: "#FFFFFF" }}
                >
                  {m}
                </th>
              ))}
              <th
                className="px-2 py-1.5 text-right font-semibold whitespace-nowrap"
                style={{ background: DARK_BG, color: "#FFFFFF" }}
              >
                TOTAL
              </th>
            </tr>
          </thead>
          <tbody>
            {years.map((y, i) => (
              <YearRows key={y.year} year={y} first={i === 0} colSpan={months.length + 2} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-gray-500 leading-relaxed mt-3">
        Valores em R$. Cores pelo crescimento vs o ano anterior (verde &gt;= 30%, âmbar
        0-30%, vermelho queda). % mês = vs mesmo mês do ano anterior. % acum = acumulado no
        ano vs mesmo período.
      </p>
    </Card>
  );
}

function YearRows({ year, first, colSpan }: { year: FatYear; first: boolean; colSpan: number }) {
  const rows: ReactElement[] = [];

  // 0. Espaçador entre anos (não antes do primeiro) — separa visualmente os blocos.
  if (!first) {
    rows.push(
      <tr key={`${year.year}-spacer`} aria-hidden>
        <td colSpan={colSpan} style={{ height: 14, padding: 0, background: "transparent" }} />
      </tr>
    );
  }

  // 1. Linha de valor (negrito)
  rows.push(
    <tr key={`${year.year}-val`} className="border-t-2 border-gray-300">
      <td
        className={`${LABEL} font-bold`}
        style={{ background: "#FFFFFF", color: "#15151F" }}
      >
        {year.year}
      </td>
      {year.values.map((c, i) => {
        if (c.future) return <td key={i} className={TD} />;
        const cor = corYoY(c.yoy_pct);
        return (
          <td
            key={i}
            className={`${TD} font-bold`}
            style={{ background: cor.bg, color: cor.fg }}
          >
            {brlBare(c.value)}
          </td>
        );
      })}
      <td
        className={`${TD} font-bold`}
        style={{ background: DARK_BG, color: "#FFFFFF" }}
      >
        {brlBare(year.value_total)}
      </td>
    </tr>
  );

  // 2. Linha "% mês" (só se tem_yoy)
  if (year.tem_yoy) {
    rows.push(
      <tr key={`${year.year}-pmes`}>
        <td className={`${LABEL} text-gray-500`}>% mês</td>
        {(year.yoy_mes ?? []).map((c, i) => {
          if (c.future || c.pct == null) return <td key={i} className={`${TD} text-gray-400`} />;
          const cor = corYoY(c.pct);
          return (
            <td key={i} className={TD} style={{ background: cor.bg, color: cor.fg }}>
              {pctTxt(c.pct)}
            </td>
          );
        })}
        <td className={`${TD} text-gray-600`}>
          {year.yoy_total == null ? "" : pctTxt(year.yoy_total)}
        </td>
      </tr>
    );
  }

  // 3. Linha "acum." (sem cor)
  rows.push(
    <tr key={`${year.year}-acum`}>
      <td className={`${LABEL} text-gray-500`}>acum.</td>
      {year.acum.map((c, i) =>
        c.future ? (
          <td key={i} className={`${TD} text-gray-400`} />
        ) : (
          <td key={i} className={`${TD} text-gray-600`}>
            {brlBare(c.value)}
          </td>
        )
      )}
      <td className={TD} />
    </tr>
  );

  // 4. Linha "% acum." (só se tem_yoy)
  if (year.tem_yoy) {
    rows.push(
      <tr key={`${year.year}-pacum`}>
        <td className={`${LABEL} text-gray-500`}>% acum.</td>
        {(year.yoy_acum ?? []).map((c, i) => {
          if (c.future || c.pct == null) return <td key={i} className={`${TD} text-gray-400`} />;
          const cor = corYoY(c.pct);
          return (
            <td key={i} className={TD} style={{ background: cor.bg, color: cor.fg }}>
              {pctTxt(c.pct)}
            </td>
          );
        })}
        <td className={TD} />
      </tr>
    );
  }

  return <>{rows}</>;
}
