import { useState } from "react";
import type { ReactNode } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { PageHeader, Tabs } from "../components/layout";
import {
  KpiCard, Caption, Card, ChartTitle, Select, DataTable, Spinner, ErrorBox, InfoBox,
  type Column,
} from "../components/ui";
import { fmtBRL, fmtNum, fmtPct, fmtCompact, tipBRL } from "../lib/format";
import { getVisiblePageTabs } from "../lib/accessCatalog";
import { useAuth } from "../lib/auth";
import type { Variant } from "../theme";
import {
  useFinKpis, useFinDre, useFinContasReceber, useFinContasPagar, useFinLiquidacoes, useFinFluxo,
  type FinKpisData, type FinDreData, type FinContasData, type FinLiqData, type FinFluxoData,
} from "../lib/api";

// Eixo Y dos gráficos monetários (sem o prefixo "R$ ").
const axisFmt = (v: number) => fmtCompact(v).replace("R$ ", "");

// Normaliza o variant que vem do backend para o tipo Variant do front.
// "neutral" (ou qualquer valor não mapeado) vira "" (sem cor de destaque).
function toVariant(v: string | null | undefined): Variant {
  return v === "success" || v === "warning" || v === "danger" ? v : "";
}

// Direção do delta como esperado pelo KpiCard.
function toDir(v: string | null | undefined): "up" | "down" | "flat" {
  return v === "up" || v === "down" ? v : "flat";
}

// "YYYY-MM-DD..." -> "YYYY-MM" para rótulos de eixo.
const mesLabel = (m: string) => m.slice(0, 7);

// Converte input <input type="month"> ("YYYY-MM") para "YYYY-MM-01" (ou undefined).
const mesParam = (m: string): string | undefined => (m ? `${m}-01` : undefined);

// Paleta índigo/roxo derivada para a pizza da DRE (cicla se houver mais grupos).
const PIZZA_CORES = ["#1E1882", "#4844C8", "#7A7AC8", "#0D8B92", "#7030A0", "#C55A11", "#6B7280"];

const REGIME_OPTS = [
  { value: "CAIXA", label: "Caixa" },
  { value: "COMPETENCIA", label: "Competência" },
];

export default function Financeiro() {
  const { user } = useAuth();
  const [tab, setTab] = useState("kpis");
  const [regime, setRegime] = useState("CAIXA");
  const [de, setDe] = useState("");
  const [ate, setAte] = useState("");
  const tabs = getVisiblePageTabs("/financeiro", user);
  const tabAtiva = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id;

  const ini = mesParam(de);
  const fim = mesParam(ate);

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader
        title="💰 Financeiro"
        subtitle="O caixa, o resultado e as pontes entre eles."
        sources={[{ name: "ERP", active: true }]}
      />

      {/* Filtros globais (afetam KPIs e DRE) */}
      <div className="flex flex-wrap items-end gap-4 mb-5">
        <div className="w-52">
          <Select label="Regime" value={regime} onChange={setRegime} options={REGIME_OPTS} />
        </div>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-gray-500">De</span>
          <input
            type="month"
            value={de}
            max={ate || undefined}
            onChange={(e) => setDe(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800
                       focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882] cursor-pointer"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-gray-500">Até</span>
          <input
            type="month"
            value={ate}
            min={de || undefined}
            onChange={(e) => setAte(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800
                       focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882] cursor-pointer"
          />
        </label>
        <p className="text-[11px] text-gray-400 pb-2.5">
          Regime e período aplicam-se apenas às abas KPIs e DRE.
        </p>
      </div>

      {tabs.length === 0 ? (
        <InfoBox>Nenhuma aba financeira está habilitada para o seu usuário.</InfoBox>
      ) : (
        <>
          <Tabs tabs={tabs} active={tabAtiva} onChange={setTab} />

          {tabAtiva === "kpis" && <KpisTab regime={regime} ini={ini} fim={fim} />}
          {tabAtiva === "dre" && <DreTab regime={regime} ini={ini} fim={fim} />}
          {tabAtiva === "cr" && <ContasTab modo="receber" />}
          {tabAtiva === "cp" && <ContasTab modo="pagar" />}
          {tabAtiva === "liq" && <LiquidacoesTab />}
          {tabAtiva === "fluxo" && <FluxoTab />}
        </>
      )}
    </div>
  );
}

// ── Wrapper padrão (Spinner / ErrorBox / InfoBox de vazio) ─────
function Loader<T extends { empty: boolean }>({
  isLoading, error, data, children,
}: {
  isLoading: boolean;
  error: unknown;
  data: T | undefined;
  children: (d: T) => ReactNode;
}) {
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox message={(error as Error).message} />;
  if (!data || data.empty) return <InfoBox>Sem dados no período.</InfoBox>;
  return <>{children(data)}</>;
}

// ── Aba KPIs ──────────────────────────────────────────────────
function KpisTab({ regime, ini, fim }: { regime: string; ini?: string; fim?: string }) {
  const q = useFinKpis(regime, ini, fim);
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <KpisContent data={d} />}
    </Loader>
  );
}

function KpisContent({ data }: { data: FinKpisData }) {
  const nMeses = data.serie.length;
  const cores = data.serie_meta.cores;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {data.cards.map((c) => (
          <KpiCard
            key={c.field}
            label={c.label}
            value={fmtBRL(c.valor)}
            delta={c.mom_pct != null ? fmtPct(c.mom_pct) : undefined}
            deltaDir={toDir(c.dir)}
            variant={toVariant(c.variant)}
          />
        ))}
      </div>

      {data.mes_corrente_parcial && <Caption>O mês corrente é parcial.</Caption>}

      <Card>
        <ChartTitle>Evolução de KPIs — {nMeses} meses</ChartTitle>
        <ResponsiveContainer width="100%" height={340}>
          <LineChart
            data={data.serie.map((s) => ({ ...s, mes: mesLabel(s.mes) }))}
            margin={{ top: 12, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipBRL} />
            <Legend />
            <Line
              type="monotone" dataKey="faturamento" name="Faturamento"
              stroke={cores.faturamento ?? "#1E1882"} strokeWidth={2}
              dot={false} isAnimationActive={false}
            />
            <Line
              type="monotone" dataKey="margem_bruta" name="Margem Bruta"
              stroke={cores.margem_bruta ?? "#10B981"} strokeWidth={2}
              dot={false} isAnimationActive={false}
            />
            <Line
              type="monotone" dataKey="ebitda" name="EBITDA"
              stroke={cores.ebitda ?? "#F59E0B"} strokeWidth={2}
              dot={false} isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}

// ── Aba DRE ───────────────────────────────────────────────────
function DreTab({ regime, ini, fim }: { regime: string; ini?: string; fim?: string }) {
  const [mesSel, setMesSel] = useState<string | undefined>(undefined);
  const q = useFinDre(regime, ini, fim, mesSel);
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <DreContent data={d} mesSel={mesSel} onMes={setMesSel} />}
    </Loader>
  );
}

function DreContent({
  data, mesSel, onMes,
}: {
  data: FinDreData; mesSel?: string; onMes: (m: string) => void;
}) {
  const mesOpts = data.meses_disponiveis.map((m) => ({ value: m, label: m.slice(0, 7) }));
  const linhaCols: Column<FinDreData["linhas"][number]>[] = [
    { key: "grupo_dre", header: "Grupo" },
    { key: "descricao", header: "Descrição" },
    {
      key: "valor", header: "Valor", align: "right",
      render: (r) => <span className={r.valor < 0 ? "text-red-600" : ""}>{fmtBRL(r.valor)}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="w-64">
        <Select
          label="Mês de referência"
          value={mesSel ?? data.mes_selecionado ?? ""}
          onChange={onMes}
          options={mesOpts}
        />
      </div>

      <Card>
        <ChartTitle>Demonstrativo de Resultado</ChartTitle>
        <DataTable columns={linhaCols} rows={data.linhas} />
      </Card>

      {data.pizza.length > 0 && (
        <Card>
          <ChartTitle>Composição da DRE (magnitude por grupo)</ChartTitle>
          <ResponsiveContainer width="100%" height={360}>
            <PieChart>
              <Pie
                data={data.pizza.map((p) => ({ ...p, valor: Math.abs(p.valor) }))}
                dataKey="valor"
                nameKey="grupo_dre"
                cx="50%"
                cy="50%"
                outerRadius={120}
                isAnimationActive={false}
              >
                {data.pizza.map((p, i) => (
                  <Cell key={p.grupo_dre} fill={PIZZA_CORES[i % PIZZA_CORES.length]} />
                ))}
              </Pie>
              <Tooltip formatter={tipBRL} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}

// ── Abas Contas a Receber / a Pagar ───────────────────────────
function ContasTab({ modo }: { modo: "receber" | "pagar" }) {
  const receber = modo === "receber";
  const qCR = useFinContasReceber();
  const qCP = useFinContasPagar();
  const q = receber ? qCR : qCP;
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <ContasContent data={d} receber={receber} />}
    </Loader>
  );
}

function ContasContent({ data, receber }: { data: FinContasData; receber: boolean }) {
  const r = data.resumo;
  const sufixo = receber ? "a Receber" : "a Pagar";
  const barCor = receber ? "#1E1882" : "#4844C8";
  const totalVariant: Variant = receber ? "" : "warning";

  const cols: Column<FinContasData["titulos_sample"][number]>[] = [
    { key: "title_number", header: "Título" },
    { key: "partner_name", header: receber ? "Cliente" : "Fornecedor" },
    { key: "vencimento", header: "Vencimento" },
    { key: "valor", header: "Valor", align: "right", render: (t) => fmtBRL(t.valor) },
    { key: "group_name", header: "Grupo" },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label={`Total ${sufixo}`} value={fmtBRL(r.total)} variant={totalVariant} />
        <KpiCard label="Títulos" value={fmtNum(r.titulos)} />
        <KpiCard label="Vencido" value={fmtBRL(r.vencido)} variant="danger" />
        <KpiCard
          label="% Vencido"
          value={`${fmtNum(r.pct_vencido, 1)}%`}
          variant={toVariant(r.pct_variant)}
        />
      </div>

      <Card>
        <ChartTitle>{`${receber ? "Recebíveis" : "Pagamentos"} por Vencimento`}</ChartTitle>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data.por_vencimento} margin={{ top: 12, right: 16, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipBRL} />
            <Bar dataKey="valor" fill={barCor} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <Card>
        <ChartTitle>{`Amostra de títulos ${sufixo.toLowerCase()}`}</ChartTitle>
        <DataTable columns={cols} rows={data.titulos_sample} />
      </Card>
    </div>
  );
}

// ── Aba Liquidações ───────────────────────────────────────────
function LiquidacoesTab() {
  const q = useFinLiquidacoes();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <LiquidacoesContent data={d} />}
    </Loader>
  );
}

interface LiqPivot {
  mes: string;
  RECEBIMENTO: number;
  PAGAMENTO: number;
}

function LiquidacoesContent({ data }: { data: FinLiqData }) {
  // Pivota por_mes em { mes, RECEBIMENTO, PAGAMENTO } preservando a ordem dos meses.
  const pivot = Object.values(
    data.por_mes.reduce<Record<string, LiqPivot>>((acc, row) => {
      const cur = acc[row.mes] ?? (acc[row.mes] = { mes: row.mes, RECEBIMENTO: 0, PAGAMENTO: 0 });
      if (row.tipo_liquidacao === "RECEBIMENTO") cur.RECEBIMENTO += row.valor_liquidado;
      else if (row.tipo_liquidacao === "PAGAMENTO") cur.PAGAMENTO += row.valor_liquidado;
      return acc;
    }, {}),
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total Liquidado" value={fmtBRL(data.resumo.total_liquidado)} variant="success" />
        <KpiCard label="Liquidações" value={fmtNum(data.resumo.qtd)} />
      </div>

      <Card>
        <ChartTitle>Liquidações por Mês</ChartTitle>
        <ResponsiveContainer width="100%" height={340}>
          <BarChart data={pivot} margin={{ top: 12, right: 16, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipBRL} />
            <Legend />
            <Bar dataKey="RECEBIMENTO" name="Recebimento" stackId="liq" fill="#10B981" isAnimationActive={false} />
            <Bar dataKey="PAGAMENTO" name="Pagamento" stackId="liq" fill="#DC2626" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}

// ── Aba Fluxo de Caixa ────────────────────────────────────────
function FluxoTab() {
  const q = useFinFluxo();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <FluxoContent data={d} />}
    </Loader>
  );
}

function FluxoContent({ data }: { data: FinFluxoData }) {
  const r = data.resumo;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Saldo Acumulado" value={fmtBRL(r.saldo_acumulado)} />
        <KpiCard
          label="Saldo Último Mês"
          value={fmtBRL(r.saldo_ultimo_mes)}
          variant={toVariant(r.saldo_ultimo_variant)}
        />
      </div>

      <Card>
        <ChartTitle>Entradas × Saídas × Saldo por Mês</ChartTitle>
        <ResponsiveContainer width="100%" height={340}>
          <BarChart data={data.por_mes} margin={{ top: 12, right: 16, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipBRL} />
            <Legend />
            <Bar dataKey="entradas" name="Entradas" fill="#10B981" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="saidas" name="Saídas" fill="#DC2626" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="saldo" name="Saldo" fill="#1E1882" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
