import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { PageHeader, Tabs } from "../components/layout";
import {
  KpiCard, SectionTitle, Caption, Card, ChartTitle, Select, DataTable, Spinner, ErrorBox, InfoBox,
  type Column,
} from "../components/ui";
import { fmtNum } from "../lib/format";
import { getVisiblePageTabs } from "../lib/accessCatalog";
import { useAuth } from "../lib/auth";
import {
  useEngCatalogo, useEngItens, useEngBom, useEngExplosao, useEngRoadmap,
  type EngCatalogo, type EngItens, type EngItem, type EngBom, type EngBomLinha,
  type EngExplosao, type EngRoadmap,
} from "../lib/api";

// Formatter de tooltip do Recharts para quantidades (param largo p/ casar com ValueType).
const tipNum = (v: unknown): string => fmtNum(Number(v));

// Trunca nomes longos de grupo para caber no eixo.
const trunc = (s: string, n = 22) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

export default function Engenharia() {
  const { user } = useAuth();
  const [tab, setTab] = useState("catalogo");
  const tabs = getVisiblePageTabs("/engenharia", user);
  const tabAtiva = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id;

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader
        title="Engenharia e P&D"
        subtitle="O catálogo de produtos, a estrutura técnica e o P&D que vem por aí."
        sources={[
          { name: "ERP", active: true },
          { name: "Miro", active: false },
          { name: "ClickUp", active: false },
        ]}
      />

      {tabs.length === 0 ? (
        <InfoBox>Nenhuma aba de engenharia está habilitada para o seu usuário.</InfoBox>
      ) : (
        <>
          <Tabs tabs={tabs} active={tabAtiva} onChange={setTab} />

          {tabAtiva === "catalogo" && <CatalogoTab />}
          {tabAtiva === "bom" && <BomTab />}
          {tabAtiva === "roadmap" && <RoadmapTab />}
        </>
      )}
    </div>
  );
}

// ── Wrapper padrão (Spinner / ErrorBox / conteúdo) ────────────
function Loader<T>({
  isLoading, error, data, children,
}: {
  isLoading: boolean;
  error: unknown;
  data: T | undefined;
  children: (d: T) => ReactNode;
}) {
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox message={(error as Error).message} />;
  if (!data) return <InfoBox>Sem dados disponíveis.</InfoBox>;
  return <>{children(data)}</>;
}

// ── Aba Catálogo de Produtos ──────────────────────────────────
function CatalogoTab() {
  const q = useEngCatalogo();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <CatalogoContent data={d} />}
    </Loader>
  );
}

function CatalogoContent({ data }: { data: EngCatalogo }) {
  const k = data.kpis;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total SKUs" value={fmtNum(k.total_skus)} />
        <KpiCard label="Ativos" value={fmtNum(k.ativos)} variant="success" />
        <div>
          <KpiCard
            label="Famílias"
            value={data.familias_disponivel ? fmtNum(k.familias) : "—"}
          />
          {!data.familias_disponivel && (
            <Caption>Indisponível: family_code não populado no ETL.</Caption>
          )}
        </div>
        <KpiCard label="Grupos" value={fmtNum(k.grupos)} />
      </div>

      {data.avisos.length > 0 && (
        <InfoBox>
          <p className="font-semibold mb-1">Cobertura de dados</p>
          <ul className="list-disc pl-5 space-y-0.5">
            {data.avisos.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </InfoBox>
      )}

      <Card>
        <ChartTitle>Mix por Grupo</ChartTitle>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={data.mix_grupo.map((m) => ({ ...m, group_name: trunc(m.group_name) }))}
            margin={{ top: 12, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="group_name" tick={{ fontSize: 11, fill: "#6B7280" }} interval={0} angle={-20} textAnchor="end" height={70} />
            <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipNum} />
            <Bar dataKey="qtd" name="SKUs" fill="#1E1882" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <SectionTitle>Busca de Itens</SectionTitle>
      <ItensBusca />
    </div>
  );
}

// ── Busca paginada de itens (carga própria) ───────────────────
function ItensBusca() {
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [page, setPage] = useState(1);

  // Debounce de 400ms na busca; volta para a primeira página a cada nova query.
  useEffect(() => {
    const t = setTimeout(() => {
      setQDebounced(q);
      setPage(1);
    }, 400);
    return () => clearTimeout(t);
  }, [q]);

  const query = useEngItens(qDebounced, page, 50);

  return (
    <div className="flex flex-col gap-4">
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Buscar por código ou nome do item..."
        className="w-full max-w-md rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800
                   focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882]"
      />
      <Loader isLoading={query.isLoading} error={query.error} data={query.data}>
        {(d) => <ItensTabela data={d} page={page} onPage={setPage} />}
      </Loader>
    </div>
  );
}

function ItensTabela({
  data, page, onPage,
}: {
  data: EngItens; page: number; onPage: (p: number) => void;
}) {
  const totalPaginas = Math.max(1, Math.ceil(data.total / data.page_size));
  const cols: Column<EngItem>[] = [
    { key: "item_code", header: "Código" },
    { key: "item_name", header: "Item" },
    { key: "group_name", header: "Grupo" },
    { key: "net_weight", header: "Peso Líq.", align: "right", render: (i) => fmtNum(i.net_weight, 2) },
    { key: "is_active", header: "Ativo", render: (i) => (i.is_active ? "Sim" : "Não") },
  ];

  return (
    <div className="flex flex-col gap-3">
      <Caption>{fmtNum(data.total)} resultados</Caption>
      <Card>
        <DataTable columns={cols} rows={data.itens} />
      </Card>
      <div className="flex items-center gap-3">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700
                     hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Anterior
        </button>
        <span className="text-sm text-gray-500">
          Página {fmtNum(page)} de {fmtNum(totalPaginas)}
        </span>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPaginas}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700
                     hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Próxima
        </button>
      </div>
    </div>
  );
}

// ── Aba Estrutura Técnica (BOM) ───────────────────────────────
function BomTab() {
  const [itemCode, setItemCode] = useState<string | undefined>(undefined);
  const q = useEngBom(itemCode || undefined);
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <BomContent data={d} itemCode={itemCode} onItemCode={setItemCode} />}
    </Loader>
  );
}

function BomContent({
  data, itemCode, onItemCode,
}: {
  data: EngBom; itemCode?: string; onItemCode: (c: string) => void;
}) {
  const [mostrarExplosao, setMostrarExplosao] = useState(false);
  const k = data.kpis;
  const produtoOpts = [
    { value: "", label: "Todos" },
    ...data.produtos.map((p) => ({ value: p, label: p })),
  ];
  const cols: Column<EngBomLinha>[] = [
    { key: "produto_pai", header: "Produto Pai" },
    { key: "componente", header: "Componente" },
    { key: "child_item_code", header: "Cód. Filho" },
    { key: "quantity", header: "Qtd", align: "right", render: (l) => fmtNum(l.quantity, 4) },
    { key: "link_label", header: "Tipo" },
  ];

  return (
    <div className="flex flex-col gap-5">
      <div className="w-72">
        <Select
          label="Produto"
          value={itemCode ?? ""}
          onChange={(v) => {
            onItemCode(v);
            setMostrarExplosao(false);
          }}
          options={produtoOpts}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Produtos com BOM" value={fmtNum(k.produtos_com_bom)} />
        <KpiCard label="Relações BOM" value={fmtNum(k.relacoes_bom)} />
      </div>

      <Card>
        <ChartTitle>Estrutura de Materiais</ChartTitle>
        <DataTable columns={cols} rows={data.linhas} />
      </Card>

      {itemCode && (
        <div className="flex flex-col gap-4">
          {!mostrarExplosao && (
            <button
              onClick={() => setMostrarExplosao(true)}
              className="self-start rounded-lg bg-[#1E1882] px-4 py-2 text-sm font-semibold text-white
                         hover:bg-[#2C28A8] transition-colors"
            >
              Explodir estrutura (multi-nível)
            </button>
          )}
          {mostrarExplosao && <ExplosaoBloco itemCode={itemCode} />}
        </div>
      )}
    </div>
  );
}

// ── Explosão multi-nível (carga própria) ──────────────────────
function ExplosaoBloco({ itemCode }: { itemCode: string }) {
  const q = useEngExplosao(itemCode);
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <ExplosaoArvore data={d} />}
    </Loader>
  );
}

function ExplosaoArvore({ data }: { data: EngExplosao }) {
  if (data.niveis.length === 0) {
    return <InfoBox>Este produto não possui estrutura multi-nível.</InfoBox>;
  }
  return (
    <Card>
      <ChartTitle>Explosão multi-nível — {data.item_code ?? "—"}</ChartTitle>
      <ul className="flex flex-col gap-1">
        {data.niveis.map((n, i) => (
          <li
            key={`${n.child_item_code}-${i}`}
            className="flex items-baseline gap-2 py-1 border-b border-gray-100 last:border-b-0"
            style={{ paddingLeft: n.nivel * 16 }}
          >
            <span className="text-sm text-gray-800">
              {n.componente}
              <span className="text-gray-400"> ({n.child_item_code})</span>
            </span>
            <span className="text-sm tabular-nums text-gray-600">×{fmtNum(n.quantity, 4)}</span>
            <span className="text-xs text-gray-400 truncate">{n.path}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ── Aba Roadmap P&D ───────────────────────────────────────────
function RoadmapTab() {
  const q = useEngRoadmap();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <RoadmapContent data={d} />}
    </Loader>
  );
}

function RoadmapContent({ data }: { data: EngRoadmap }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
      <div className="flex items-center justify-center gap-2 mb-4">
        <span className="text-5xl">🔬</span>
        <span className="text-4xl">🚧</span>
      </div>
      <span className="inline-block rounded-full bg-[#EEF0FF] text-[#1E1882] text-xs font-semibold px-3 py-0.5 mb-3">
        Placeholder
      </span>
      <p className="text-lg font-semibold text-gray-700">{data.titulo}</p>
      <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">{data.mensagem}</p>

      {data.kpis_planejados.length > 0 && (
        <div className="mt-6 max-w-md mx-auto text-left">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
            KPIs planejados
          </p>
          <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
            {data.kpis_planejados.map((kpi) => (
              <li key={kpi}>{kpi}</li>
            ))}
          </ul>
        </div>
      )}

      {data.fontes_a_integrar.length > 0 && (
        <div className="mt-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
            Fontes a integrar
          </p>
          <div className="flex flex-wrap gap-2 justify-center">
            {data.fontes_a_integrar.map((f) => (
              <span
                key={f}
                className="inline-flex items-center gap-1.5 rounded-full bg-[#F0F0F8] text-gray-600 text-xs font-medium px-3 py-1"
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
