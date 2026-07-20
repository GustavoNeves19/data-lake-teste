import { useState } from "react";
import type { ReactNode } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { PageHeader, Tabs } from "../components/layout";
import {
  KpiCard, SectionTitle, Caption, Card, ChartTitle, Select, DataTable, Spinner, ErrorBox, InfoBox,
  type Column,
} from "../components/ui";
import { fmtNum } from "../lib/format";
import { getVisiblePageTabs } from "../lib/accessCatalog";
import { useAuth } from "../lib/auth";
import type { Variant } from "../theme";
import {
  useOpProducao, useOpComponentes, useOpEstoque, useOpMovimentacao, useOpBom,
  type OpProducao, type OpComponentes, type OpEstoque, type OpMovimentacao, type OpBom,
} from "../lib/api";

// Formatter de tooltip do Recharts para quantidades (param largo p/ casar com ValueType).
const tipNum = (v: unknown): string => fmtNum(Number(v));

// "YYYY-MM-DD..." -> "YYYY-MM" para rótulos de eixo.
const mesLabel = (m: string) => m.slice(0, 7);

// Trunca nomes longos de item para caber no eixo/tabela.
const trunc = (s: string, n = 28) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

// Paleta índigo/roxos ciclada para a pizza de status das OPs.
const STATUS_CORES = ["#1E1882", "#4844C8", "#7A7AC8", "#7030A0", "#9D4EDD", "#5A55D6", "#6B7280"];

// Eficiência global vira variant por faixa.
function eficienciaVariant(pct: number): Variant {
  if (pct >= 90) return "success";
  if (pct >= 70) return "warning";
  return "danger";
}

export default function Operacional() {
  const { user } = useAuth();
  const [tab, setTab] = useState("producao");
  const tabs = getVisiblePageTabs("/operacional", user);
  const tabAtiva = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id;

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader
        title="Operacional e Produção"
        subtitle="Ordens de produção, estoque e a estrutura de material."
        sources={[{ name: "ERP", active: true }]}
      />

      {tabs.length === 0 ? (
        <InfoBox>Nenhuma aba operacional está habilitada para o seu usuário.</InfoBox>
      ) : (
        <>
          <Tabs tabs={tabs} active={tabAtiva} onChange={setTab} />

          {tabAtiva === "producao" && <ProducaoTab />}
          {tabAtiva === "estoque" && <EstoqueTab />}
          {tabAtiva === "bom" && <BomTab />}
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

// ── Aba Ordens de Produção ────────────────────────────────────
function ProducaoTab() {
  const q = useOpProducao();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <ProducaoContent data={d} />}
    </Loader>
  );
}

function ProducaoContent({ data }: { data: OpProducao }) {
  const k = data.kpis;
  return (
    <div className="flex flex-col gap-5">
      <Caption>Produção é dado esparso (poucas OPs).</Caption>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total OPs" value={fmtNum(k.total_ops)} />
        <KpiCard label="Qtd. Planejada" value={fmtNum(k.qtd_planejada)} />
        <KpiCard label="Qtd. Produzida" value={fmtNum(k.qtd_produzida)} />
        <KpiCard
          label="Eficiência Global"
          value={`${fmtNum(k.eficiencia_global, 1)}%`}
          variant={eficienciaVariant(k.eficiencia_global)}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <ChartTitle>Planejado × Produzido por Mês</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart
              data={data.planejado_produzido.map((m) => ({ ...m, mes: mesLabel(m.mes) }))}
              margin={{ top: 12, right: 16, left: 8, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
              <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
              <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
              <Tooltip formatter={tipNum} />
              <Legend />
              <Bar dataKey="qtd_planejada" name="Planejado" fill="#1E1882" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="qtd_produzida" name="Produzido" fill="#10B981" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <ChartTitle>OPs por Status</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={data.por_status}
                dataKey="qtd_op"
                nameKey="status_label"
                cx="50%"
                cy="50%"
                outerRadius={110}
                isAnimationActive={false}
              >
                {data.por_status.map((s, i) => (
                  <Cell key={s.prod_status} fill={STATUS_CORES[i % STATUS_CORES.length]} />
                ))}
              </Pie>
              <Tooltip formatter={tipNum} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <SectionTitle>Top 20 Componentes Consumidos</SectionTitle>
      <ComponentesTable />
    </div>
  );
}

// ── Componentes consumidos (carga própria) ────────────────────
function ComponentesTable() {
  const q = useOpComponentes();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <ComponentesContent data={d} />}
    </Loader>
  );
}

function ComponentesContent({ data }: { data: OpComponentes }) {
  const cols: Column<OpComponentes["componentes"][number]>[] = [
    { key: "item_nome", header: "Item", render: (c) => trunc(c.item_nome) },
    { key: "consumido", header: "Consumido", align: "right", render: (c) => fmtNum(c.consumido) },
    { key: "planejado", header: "Planejado", align: "right", render: (c) => fmtNum(c.planejado) },
  ];
  return (
    <Card>
      <DataTable columns={cols} rows={data.componentes} />
    </Card>
  );
}

// ── Aba Estoque ───────────────────────────────────────────────
function EstoqueTab() {
  const q = useOpEstoque();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <EstoqueContent data={d} />}
    </Loader>
  );
}

function EstoqueContent({ data }: { data: OpEstoque }) {
  const k = data.kpis;
  const cols: Column<OpEstoque["itens"][number]>[] = [
    { key: "item_code", header: "Código" },
    { key: "item_nome", header: "Item" },
    { key: "group_name", header: "Grupo" },
    { key: "saldo", header: "Saldo", align: "right", render: (i) => fmtNum(i.saldo) },
  ];
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <KpiCard label="Itens em Estoque" value={fmtNum(k.itens)} />
        <KpiCard label="Total Qtd" value={fmtNum(k.total_qtd)} />
        <KpiCard label="Grupos" value={fmtNum(k.grupos)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <ChartTitle>Estoque por Grupo</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={data.por_grupo}
                dataKey="saldo"
                nameKey="group_name"
                cx="50%"
                cy="50%"
                outerRadius={110}
                isAnimationActive={false}
              >
                {data.por_grupo.map((g, i) => (
                  <Cell key={g.group_name} fill={STATUS_CORES[i % STATUS_CORES.length]} />
                ))}
              </Pie>
              <Tooltip formatter={tipNum} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <MovimentacaoCard />
      </div>

      <Card>
        <ChartTitle>Itens em Estoque (top 300)</ChartTitle>
        <DataTable columns={cols} rows={data.itens.slice(0, 300)} />
      </Card>
    </div>
  );
}

// ── Movimentação (carga própria, dentro da aba Estoque) ───────
function MovimentacaoCard() {
  const q = useOpMovimentacao();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <MovimentacaoContent data={d} />}
    </Loader>
  );
}

function MovimentacaoContent({ data }: { data: OpMovimentacao }) {
  return (
    <Card>
      <ChartTitle>Entradas × Saídas por Mês</ChartTitle>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart
          data={data.series.map((s) => ({ ...s, mes: mesLabel(s.mes) }))}
          margin={{ top: 12, right: 16, left: 8, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
          <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
          <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
          <Tooltip formatter={tipNum} />
          <Legend />
          <Bar dataKey="entradas" name="Entradas" fill="#10B981" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="saidas" name="Saídas" fill="#DC2626" radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

// ── Aba BOM ───────────────────────────────────────────────────
function BomTab() {
  const [parent, setParent] = useState<string | undefined>(undefined);
  const q = useOpBom(parent || undefined);
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <BomContent data={d} parent={parent} onParent={setParent} />}
    </Loader>
  );
}

function BomContent({
  data, parent, onParent,
}: {
  data: OpBom; parent?: string; onParent: (p: string) => void;
}) {
  const k = data.kpis;
  const parentOpts = [
    { value: "", label: "Todos" },
    ...data.produtos_pai.map((p) => ({ value: p, label: p })),
  ];
  const cols: Column<OpBom["linhas"][number]>[] = [
    { key: "produto_pai", header: "Produto Pai" },
    { key: "parent_item_code", header: "Cód. Pai" },
    { key: "componente", header: "Componente" },
    { key: "child_item_code", header: "Cód. Filho" },
    { key: "quantity", header: "Qtd", align: "right", render: (l) => fmtNum(l.quantity, 4) },
  ];
  return (
    <div className="flex flex-col gap-5">
      <div className="w-72">
        <Select label="Produto pai" value={parent ?? ""} onChange={onParent} options={parentOpts} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Produtos com BOM" value={fmtNum(k.produtos_com_bom)} />
        <KpiCard label="Relações BOM" value={fmtNum(k.relacoes)} />
      </div>

      <Card>
        <ChartTitle>Estrutura de Materiais</ChartTitle>
        <DataTable columns={cols} rows={data.linhas} />
      </Card>
    </div>
  );
}
