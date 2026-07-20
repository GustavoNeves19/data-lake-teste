import { useCalendario, type CalDia } from "../lib/api";
import { Spinner, ErrorBox, InfoBox, Card, ChartTitle } from "../components/ui";

// Moeda sem decimais, com ponto de milhar.
const brl0 = (v: number) => "R$ " + Math.round(v).toLocaleString("pt-BR");
const brlBare = (v: number) => brl0(v).replace("R$ ", "");

// ── Chip de valor diário ──────────────────────────────────────
function ValueChip({ value, hit }: { value: number; hit?: boolean | null }) {
  let bg = "#EEF0F6";
  let fg = "#3C3489";
  if (hit === true) {
    bg = "#10B981";
    fg = "#FFFFFF";
  } else if (hit === false) {
    bg = "#FDE68A";
    fg = "#8A5A00";
  }
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold leading-none"
      style={{ background: bg, color: fg }}
    >
      {brlBare(value)}
    </span>
  );
}

// ── Célula de dia ─────────────────────────────────────────────
function DayCell({ cell }: { cell: CalDia }) {
  if (cell.empty) {
    return <td className="align-top p-1.5 h-16" style={{ background: "#FAFAFC" }} />;
  }
  return (
    <td className="align-top p-1.5 h-16 border border-[#F0F0F8]">
      <div className="text-[10px] text-gray-400 leading-none">{cell.day}</div>
      {cell.value != null && cell.value > 0 && (
        <div className="mt-1.5">
          <ValueChip value={cell.value} hit={cell.hit} />
        </div>
      )}
    </td>
  );
}

// ── Card-stat do footer ───────────────────────────────────────
function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-xl px-4 py-3 shadow-[0_2px_8px_rgba(0,0,0,0.06)] border border-[#F0F0F8]">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500 m-0">{label}</p>
      <p className="text-[20px] font-bold text-gray-900 leading-tight m-0 mt-1">{value}</p>
      {sub && <p className="text-[11px] text-gray-500 m-0 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function CalendarioVendas({ mes }: { mes: string }) {
  const { data, isLoading, error } = useCalendario(mes);

  if (isLoading) return <Spinner label="Montando o calendário de vendas..." />;
  if (error) return <ErrorBox message={(error as Error).message} />;
  if (!data) return <InfoBox>Selecione um mês para ver o calendário de vendas diárias.</InfoBox>;

  const f = data.footer;
  const pctLabel = `${Math.round(f.pct * 100)}%`;
  // Vermelho = realizado; verde = incremento da projeção (do realizado até a projeção), na trilha da meta.
  const pctRealizado = Math.min(f.pct, 1) * 100;
  const pctProjecaoInc = f.meta > 0
    ? Math.max(0, Math.min(f.projecao / f.meta, 1) - Math.min(f.pct, 1)) * 100
    : 0;

  return (
    <Card>
      <ChartTitle>{data.titulo}</ChartTitle>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              {data.weekdays.map((wd, i) => {
                const fimDeSemana = i === 0 || i === 6;
                return (
                  <th
                    key={wd}
                    className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wide text-center"
                    style={
                      fimDeSemana
                        ? { background: "#EEF0F6", color: "#3C3489" }
                        : { background: "#3C3489", color: "#FFFFFF" }
                    }
                  >
                    {wd}
                  </th>
                );
              })}
              <th
                className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wide text-center"
                style={{ background: "#2C2C3A", color: "#FFFFFF" }}
              >
                TOTAL
              </th>
            </tr>
          </thead>
          <tbody>
            {data.weeks.map((week, wi) => (
              <tr key={wi}>
                {week.cells.map((cell, ci) => (
                  <DayCell key={ci} cell={cell} />
                ))}
                <td
                  className="align-middle text-center text-[12px] font-bold text-gray-800 border border-[#F0F0F8]"
                  style={{ background: "#F7F7FB" }}
                >
                  {brlBare(week.week_total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      {f.tem_meta ? (
        <div className="mt-5 flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <StatCard
              label="Meta diária"
              value={brl0(f.meta_dia)}
              sub={`${brl0(f.meta)} ÷ ${f.du} dias úteis`}
            />
            <StatCard label="Vendas (pedidos)" value={brl0(f.vendas)} />
            <StatCard label="Meta mensal" value={brl0(f.meta)} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <StatCard
              label="Remanescente"
              value={
                f.dias_rest === 0
                  ? "—"
                  : `${brl0(f.rem_dia)}/dia, ${f.dias_rest} dias úteis`
              }
            />
            <StatCard label="Falta para a meta" value={brl0(f.rem_total)} />
            <StatCard label="Atingido" value={pctLabel} />
          </div>
          {/* Barra: vermelho = realizado (obtido), verde = projeção no ritmo (o que
              deve fechar). Igual ao original do Vinícius. */}
          <div className="relative h-6 rounded-full overflow-hidden flex" style={{ background: "#EEF0F6" }}>
            <div className="h-full" style={{ background: "#DC2626", width: `${pctRealizado}%` }} />
            <div className="h-full" style={{ background: "#10B981", width: `${pctProjecaoInc}%` }} />
            <div className="absolute inset-0 flex items-center justify-center text-[12px] font-bold text-gray-800">
              {pctLabel}
            </div>
          </div>
          <div className="flex justify-between text-[11px] text-gray-500 -mt-1">
            <span><span className="inline-block w-2 h-2 rounded-full align-middle mr-1" style={{ background: "#DC2626" }} />Realizado {brl0(f.vendas)}</span>
            <span><span className="inline-block w-2 h-2 rounded-full align-middle mr-1" style={{ background: "#10B981" }} />Projeção {brl0(f.projecao)}</span>
          </div>

          {/* Bloco Faturamento (nota emitida) — separado das vendas, igual ao original */}
          <div className="grid grid-cols-2 gap-3 mt-1">
            <StatCard label="Faturamento (nota)" value={brl0(f.faturamento)} />
            <StatCard label="Projeção do faturamento" value={brl0(f.fat_projecao)} />
          </div>
        </div>
      ) : (
        <div className="mt-5 flex flex-col gap-2">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <StatCard label="Vendas (pedidos)" value={brl0(f.vendas)} />
          </div>
          <p className="text-xs text-gray-500">
            Defina a meta do mês na Gestão à Vista.
          </p>
        </div>
      )}

      <p className="text-[11px] text-gray-400 mt-4">
        Foto da última carga; o ERP atualiza ao vivo e os números se igualam a cada carga.
      </p>
    </Card>
  );
}
