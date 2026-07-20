import {
  BarChart, Bar, LineChart, Line, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";
import { useRanking, type RankingData } from "../lib/api";
import { fmtBRL, fmtNum, fmtCompact, tipBRL } from "../lib/format";
import {
  KpiCard, SectionTitle, Caption, Card, ChartTitle, DataTable,
  Spinner, ErrorBox, InfoBox, type Column,
} from "../components/ui";

const axisFmt = (v: number) => fmtCompact(v).replace("R$ ", "");

// Cores por classe ABC (verde escuro -> claro).
const CLASSE_COR: Record<string, string> = {
  A: "#0D5C4A",
  B: "#4C9A5A",
  C: "#A3D977",
};
const corClasse = (c: string) => CLASSE_COR[c] ?? "#A3D977";

type Row = RankingData["rows"][number];

const truncar = (s: string, n = 22) => (s.length > n ? s.slice(0, n) + "…" : s);

export default function RankingTab() {
  const { data, isLoading, error } = useRanking();
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox message={(error as Error).message} />;
  if (!data || data.empty) return <InfoBox>Sem dados de ranking de clientes.</InfoBox>;

  const k = data.kpis;

  const top15 = data.rows.slice(0, 15).map((r) => ({
    ...r,
    nome_curto: truncar(r.cliente),
  }));

  const top100 = data.rows.slice(0, 100);

  const columns: Column<Row>[] = [
    { key: "posicao", header: "Posição", align: "center", render: (r) => fmtNum(r.posicao) },
    { key: "cliente", header: "Cliente" },
    { key: "city", header: "Cidade" },
    { key: "state", header: "UF", align: "center" },
    { key: "classe", header: "Classe", align: "center" },
    { key: "qtd_pedidos", header: "Pedidos", align: "right", render: (r) => fmtNum(r.qtd_pedidos) },
    { key: "faturamento", header: "Faturamento", align: "right", render: (r) => fmtBRL(r.faturamento) },
    { key: "acum_pct", header: "Acum %", align: "right", render: (r) => fmtNum(r.acum_pct, 1) + "%" },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div>
        <SectionTitle>Ranking de Clientes por Faturamento</SectionTitle>
        <Caption>
          Curva ABC/Pareto na janela de 12 meses da RFV, com clientes consolidados por nome.
          Classe A concentra os 80% iniciais da receita, B os 15% seguintes e C os 5% finais.
        </Caption>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KpiCard label="Top 100 Faturamento" value={fmtBRL(k.top100_faturamento)} />
        <KpiCard
          label="Classe A (80% receita)"
          value={`${fmtNum(k.classe_a)} clientes`}
          variant={k.classe_a <= 10 ? "warning" : ""}
        />
        <KpiCard
          label="Concentração Top 20%"
          value={fmtNum(k.concentracao_top20, 1) + "%"}
          variant={k.concentracao_top20 >= 80 ? "danger" : ""}
        />
      </div>

      {/* Top 15 — barras horizontais coloridas por classe */}
      <Card>
        <ChartTitle>Top 15 Clientes</ChartTitle>
        <ResponsiveContainer width="100%" height={520}>
          <BarChart data={top15} layout="vertical" margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#EEF0FF" />
            <XAxis type="number" tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <YAxis
              type="category"
              dataKey="nome_curto"
              width={180}
              tick={{ fontSize: 11, fill: "#374151" }}
            />
            <Tooltip
              formatter={tipBRL}
              labelFormatter={(_, p) => (p?.[0]?.payload?.cliente as string) ?? ""}
            />
            <Bar dataKey="faturamento" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {top15.map((r) => (
                <Cell key={r.posicao} fill={corClasse(r.classe)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Curva de Pareto */}
      <Card>
        <ChartTitle>Curva de Pareto — % acumulado da receita</ChartTitle>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data.rows} margin={{ top: 12, right: 16, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis
              dataKey="posicao"
              type="number"
              domain={[1, "dataMax"]}
              tick={{ fontSize: 11, fill: "#6B7280" }}
              label={{ value: "Posição do cliente", position: "insideBottom", offset: -2, fontSize: 11, fill: "#9CA3AF" }}
            />
            <YAxis
              domain={[0, 100]}
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 11, fill: "#9CA3AF" }}
            />
            <Tooltip
              formatter={(v: unknown) => [`${fmtNum(Number(v), 1)}%`, "Acumulado"]}
              labelFormatter={(l) => `Posição ${l}`}
            />
            <ReferenceLine
              y={80}
              stroke="#EF4444"
              strokeDasharray="6 4"
              label={{ value: "80%", position: "right", fontSize: 11, fill: "#EF4444" }}
            />
            <Line
              type="monotone"
              dataKey="acum_pct"
              stroke="#1E1882"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      {/* Detalhamento Top 100 */}
      <div>
        <p className="text-sm font-semibold text-gray-700 mb-2">Detalhamento — Top 100</p>
        <DataTable columns={columns} rows={top100} />
      </div>
    </div>
  );
}
