import { useEffect, useMemo, useState } from "react";
import { Tv, Download } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, LabelList,
} from "recharts";
import RfvTV from "./RfvTV";
import {
  useRfvPeriodos, useRfvCarteiras, useRfv, useRfvSegmento, useRfvAlerta,
  type RfvData, type PainelRow,
} from "../lib/api";
import { fmtBRL, fmtNum } from "../lib/format";
import {
  KpiCard, SectionTitle, Caption, Card, Select, DataTable, Spinner, ErrorBox, InfoBox, type Column,
} from "../components/ui";
import { RfvMatrix } from "../components/RfvMatrix";
import {
  REGRA_FREQ, GLOSSARIO, SEGMENT_DISPLAY, SEG_OPTIONS, SEG_VARIANT,
  ALERT_META, PAINEL_SERIES,
} from "../theme";

const FAMILIAS = ["TODOS", "HOSPITALAR", "FARMACIAS"];

export default function RfvTab() {
  const [familia, setFamilia] = useState("TODOS");
  const [carteira, setCarteira] = useState("TODOS");
  const [periodo, setPeriodo] = useState<string>("");
  const [tvMode, setTvMode] = useState(false);

  const periodos = useRfvPeriodos();
  const periodoAtivo = periodo || periodos.data?.[0]?.value || "";

  const carteiras = useRfvCarteiras(familia, periodoAtivo || undefined);
  // Reseta carteira se ela não existe mais na família/período atual
  useEffect(() => {
    if (carteiras.data && !carteiras.data.some((c) => c.value === carteira)) setCarteira("TODOS");
  }, [carteiras.data, carteira]);

  const rfv = useRfv(familia, carteira, periodoAtivo || undefined);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <SectionTitle>Matriz RFV</SectionTitle>
        {rfv.data && (
          <button
            type="button"
            onClick={() => setTvMode(true)}
            title="Abrir a Matriz RFV em tela cheia para a TV (igual à tela normal)"
            className="inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white shrink-0"
            style={{ background: "#1E1882" }}
          >
            <Tv size={16} /> Modo TV
          </button>
        )}
      </div>

      {tvMode && rfv.data && (
        <RfvTV data={rfv.data} familia={familia} carteira={carteira} periodo={periodoAtivo}
          familias={FAMILIAS}
          carteiras={carteiras.data ?? [{ value: "TODOS", label: "Todas as carteiras" }]}
          periodos={periodos.data ?? []}
          onFamilia={setFamilia} onCarteira={setCarteira} onPeriodo={setPeriodo}
          onClose={() => setTvMode(false)} />
      )}

      {/* Filtros */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl">
        <Select label="Família RFV" value={familia} onChange={setFamilia}
          options={FAMILIAS.map((f) => ({ value: f, label: f }))} />
        <Select label="Carteira" value={carteira} onChange={setCarteira}
          options={carteiras.data ?? [{ value: "TODOS", label: "Todas as carteiras" }]} />
        <Select label="Período de referência" value={periodoAtivo} onChange={setPeriodo}
          options={periodos.data ?? []} />
      </div>

      {rfv.isLoading ? (
        <Spinner />
      ) : rfv.error ? (
        <ErrorBox message={(rfv.error as Error).message} />
      ) : rfv.data ? (
        <RfvContent data={rfv.data} familia={familia} carteira={carteira} periodo={periodoAtivo} />
      ) : null}
    </div>
  );
}

// ── KPI com pill delta neutra ─────────────────────────────────
type PillVariant = "success" | "warning" | "danger" | "";
const BG_MAP: Record<PillVariant, string> = {
  success: "#ECFDF5",
  warning: "#FEF3E2",
  danger: "#FEF2F2",
  "": "#F5F5FA",
};
const FG_MAP: Record<PillVariant, string> = {
  success: "#059669",
  warning: "#B45309",
  danger: "#B91C1C",
  "": "#6B7280",
};
function KpiWithPill({
  label, value, pillVariant, pillLabel,
}: {
  label: string; value: string; pillVariant?: PillVariant; pillLabel?: string;
}) {
  const v: PillVariant = pillVariant ?? "";
  return (
    <div className="flex flex-col gap-1.5">
      <KpiCard label={label} value={value} variant="" />
      {pillLabel && (
        <div className="pl-1">
          <span
            style={{ background: BG_MAP[v], color: FG_MAP[v] }}
            className="inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold"
          >
            {pillLabel}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Conteúdo principal ────────────────────────────────────────
export function RfvContent({ data, familia, carteira, periodo }: {
  data: RfvData; familia: string; carteira: string; periodo: string;
}) {
  const k = data.kpi;
  return (
    <div className="flex flex-col gap-4">
      {/* 8 KPIs — variants neutros com pill delta semântica */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiWithPill label="Total Clientes" value={fmtNum(k.total_clientes)} />
        <KpiWithPill label="Campeões" value={fmtNum(k.campeoes)} pillVariant="success" pillLabel="Alto valor" />
        <KpiWithPill label="Fiéis" value={fmtNum(k.fieis)} pillVariant="success" pillLabel="Recorrentes" />
        <KpiWithPill label="Fiéis em Potencial" value={fmtNum(k.fp)} pillVariant="success" pillLabel="Crescendo" />
        <KpiWithPill label="Não Pode Perder" value={fmtNum(k.nao_pode_perder)} pillVariant="warning" pillLabel="Reter" />
        <KpiWithPill label="Em Risco + Hibernando" value={fmtNum(k.em_risco)} pillVariant="warning" pillLabel="Reativar" />
        <KpiWithPill label="Perdidos" value={fmtNum(k.perdidos)} pillVariant="danger" pillLabel="Churn" />
        <KpiWithPill label="Faturamento" value={fmtBRL(k.faturamento)} />
      </div>

      {/* Matriz */}
      <RfvMatrix segments={data.segments} familia={familia} />

      <Glossario familia={familia} />

      <SegmentDetail familia={familia} carteira={carteira} periodo={periodo} />

      <SalespersonPanel painel={data.painel} />

      <Alerts data={data} familia={familia} />
    </div>
  );
}

// ── Glossário ─────────────────────────────────────────────────
function Glossario({ familia }: { familia: string }) {
  return (
    <details className="rounded-lg border border-gray-200 bg-white">
      <summary className="cursor-pointer text-sm font-semibold text-gray-700 px-4 py-3">
        Glossário dos Segmentos RFV
      </summary>
      <div className="px-4 pb-4">
        <div className="bg-slate-50 border border-gray-200 rounded-lg px-3.5 py-3 mb-3 text-xs text-slate-600">
          <b>Padronização da leitura:</b> todas as definições abaixo já trazem a lógica temporal da recência.{" "}
          {REGRA_FREQ[familia] ?? REGRA_FREQ.TODOS}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {GLOSSARIO.map((g) => (
            <div key={g.seg} className="flex gap-2.5 bg-gray-50 rounded-lg px-3 py-2.5"
              style={{ borderLeft: `4px solid ${SEGMENT_DISPLAY[g.seg].bg}` }}>
              <div>
                <div className="font-bold text-[13px] text-gray-900">{g.nome}</div>
                <div className="text-xs text-gray-600 mt-0.5">{g.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}

// Gera CSV que o Excel PT-BR abre certinho: separador ';' + BOM UTF-8 (acentos).
function baixarCSV(nomeArquivo: string, cabecalho: string[], linhas: (string | number)[][]) {
  const esc = (v: string | number) => {
    const s = String(v ?? "");
    return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const conteudo = [cabecalho, ...linhas].map((l) => l.map(esc).join(";")).join("\r\n");
  const blob = new Blob(["﻿" + conteudo], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeArquivo;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Detalhe por segmento ──────────────────────────────────────
function SegmentDetail({ familia, carteira, periodo }: { familia: string; carteira: string; periodo: string }) {
  const [seg, setSeg] = useState(1);
  const { data, isLoading, error } = useRfvSegmento(seg, familia, carteira, periodo || undefined);
  const meta = GLOSSARIO.find((g) => g.seg === seg)!;

  const exportar = () => {
    if (!data?.rows?.length) return;
    baixarCSV(
      `rfv_${SEG_OPTIONS[seg].toLowerCase().replace(/\s+/g, "_")}_${familia.toLowerCase()}.csv`,
      ["Nome do Cliente", "Família", "Vendedor", "Última Compra", "Dias sem Comprar", "Frequência", "Valor Total (R$)"],
      data.rows.map((r) => [r.nome_cliente, r.familia, r.vendedor, r.ultima_compra, r.dias_sem_comprar, r.frequencia, r.valor_total]),
    );
  };

  const cols: Column<NonNullable<typeof data>["rows"][number]>[] = [
    { key: "nome_cliente", header: "Nome do Cliente" },
    { key: "familia", header: "Família" },
    { key: "vendedor", header: "Vendedor" },
    { key: "ultima_compra", header: "Última Compra", align: "center",
      sortAccessor: (r) => { const [d, m, y] = String(r.ultima_compra).split("/"); return Number(`${y}${m}${d}`) || 0; } },
    { key: "dias_sem_comprar", header: "Dias sem Comprar", align: "right", render: (r) => `${r.dias_sem_comprar} dias` },
    { key: "frequencia", header: "Frequência", align: "right", render: (r) => `${r.frequencia} pedidos` },
    { key: "valor_total", header: "Valor Total (R$)", align: "right", render: (r) => fmtBRL(r.valor_total) },
  ];

  return (
    <div>
      <SectionTitle>Detalhe por Segmento</SectionTitle>
      <Caption>Lista completa dos clientes de cada segmento.</Caption>
      <div className="grid grid-cols-1 md:grid-cols-[2fr_3fr] gap-4 items-stretch mb-4">
        <Select label="Segmento" value={String(seg)} onChange={(v) => setSeg(Number(v))}
          options={Object.entries(SEG_OPTIONS).map(([n, nome]) => ({ value: n, label: nome }))} />
        <div className="rounded-xl border border-gray-200 px-4 py-3.5 flex flex-col justify-center"
          style={{ background: "linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%)", borderLeft: `6px solid ${SEGMENT_DISPLAY[seg].bg}` }}>
          <div className="text-sm font-extrabold text-gray-900">{meta.nome}</div>
          <div className="text-xs text-gray-600 mt-1.5 leading-relaxed">{meta.desc}</div>
        </div>
      </div>

      {isLoading ? <Spinner label="Carregando clientes do segmento..." /> : error ? (
        <ErrorBox message={(error as Error).message} />
      ) : data ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <KpiCard label={SEG_OPTIONS[seg]} value={`${data.qtd} cliente${data.qtd !== 1 ? "s" : ""}`} variant={SEG_VARIANT[seg]} />
            <KpiCard label="Faturamento do Segmento" value={fmtBRL(data.faturamento)} />
            <KpiCard label="Ticket Médio no Segmento" value={fmtBRL(data.ticket)} />
          </div>
          {data.rows.length > 0 ? (
            <>
              <div className="flex items-center justify-between gap-3 mb-2">
                <Caption>Clique num cabeçalho pra ordenar (última compra, dias sem comprar, frequência, valor). Padrão: churn primeiro.</Caption>
                <button
                  type="button"
                  onClick={exportar}
                  title="Baixar a lista completa deste segmento em CSV (abre no Excel)"
                  className="inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold text-white shrink-0"
                  style={{ background: "#1E1882" }}
                >
                  <Download size={15} /> Baixar Excel
                </button>
              </div>
              <DataTable columns={cols} rows={data.rows} sortable />
            </>
          ) : (
            <InfoBox>Nenhum cliente neste segmento com os filtros selecionados.</InfoBox>
          )}
        </>
      ) : null}
    </div>
  );
}

// ── Painel por vendedor ───────────────────────────────────────
function SalespersonPanel({ painel }: { painel: PainelRow[] }) {
  const chartData = useMemo(() => painel.map((p) => ({
    ...p,
    total: PAINEL_SERIES.reduce((acc, s) => acc + (p[s.key] as number), 0),
  })), [painel]);

  if (painel.length === 0) return null;

  const crmCols: Column<PainelRow>[] = [
    { key: "vendedor", header: "Vendedor" },
    { key: "clientes", header: "Clientes", align: "right", render: (r) => fmtNum(r.clientes) },
    { key: "faturamento", header: "Fat. ERP (R$)", align: "right", render: (r) => fmtBRL(r.faturamento) },
    { key: "ticket_medio", header: "Ticket Médio", align: "right", render: (r) => fmtBRL(r.ticket_medio) },
    { key: "crm_deals", header: "CRM Deals", align: "right" },
    { key: "pipeline_crm", header: "Pipeline CRM", align: "right", render: (r) => fmtBRL(r.pipeline_crm) },
    { key: "alertas_oportunidade", header: "Oport. sem CRM", align: "right" },
    { key: "alertas_churn", header: "Churn Silencioso", align: "right" },
    { key: "clientes_fora_radar", header: "Fora do Radar", align: "right" },
  ];

  return (
    <div>
      <SectionTitle>Painel por Vendedor</SectionTitle>
      <Caption>
        Composição da carteira por vendedor — segmentos RFV e faturamento da janela selecionada. Indicadores de CRM
        (deals, pipeline, alertas) usam sempre o estado atual.
      </Caption>
      <Card className="mb-4">
        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={chartData} margin={{ top: 24, right: 8, left: 8, bottom: 4 }}>
            <XAxis dataKey="vendedor" tick={{ fontSize: 11, fill: "#374151" }} interval={0} angle={-12} textAnchor="end" height={60} />
            <YAxis hide />
            <Tooltip />
            <Legend />
            {PAINEL_SERIES.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.nome} stackId="v" fill={s.cor}>
                {i === PAINEL_SERIES.length - 1 && (
                  <LabelList dataKey="total" position="top" style={{ fontSize: 12, fontWeight: 700, fill: "#111827" }} />
                )}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </Card>
      <SectionTitle>Visão CRM por Vendedor</SectionTitle>
      <DataTable columns={crmCols} rows={painel} />
    </div>
  );
}

// ── Alertas ───────────────────────────────────────────────────
function Alerts({ data, familia }: { data: RfvData; familia: string }) {
  const [tipo, setTipo] = useState<string>("");
  const tipoAtivo = tipo || data.alertas[0]?.tipo_alerta || "";
  const det = useRfvAlerta(tipoAtivo || undefined, familia);

  if (data.alertas.length === 0) return null;

  const detCols: Column<NonNullable<typeof det.data>["rows"][number]>[] = [
    { key: "cliente", header: "Cliente" },
    { key: "familias", header: "Famílias" },
    { key: "filiais", header: "Filiais", align: "right" },
    { key: "vendedores", header: "Vendedor(es)" },
    { key: "segmentos", header: "Segmento(s) RFV" },
    { key: "faturamento", header: "Faturamento (R$)", align: "right", render: (r) => fmtBRL(r.faturamento) },
    { key: "deals_abertos", header: "Deals Abertos", align: "right" },
    { key: "pipeline_crm", header: "Pipeline CRM (R$)", align: "right", render: (r) => fmtBRL(r.pipeline_crm) },
    { key: "dias_sem_deal", header: "Dias sem Deal", align: "right", render: (r) => `${r.dias_sem_deal} dias` },
    { key: "no_crm", header: "Existe no CRM?", align: "center" },
    { key: "org_pipedrive", header: "Org. Pipedrive" },
  ];

  return (
    <div>
      <SectionTitle>Alertas de Inteligência Comercial</SectionTitle>
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-3">
        {data.alertas.slice(0, 5).map((a) => {
          const meta = ALERT_META[a.tipo_alerta] ?? { emoji: "⚠️", nome: a.tipo_alerta, variant: "" as const };
          return (
            <KpiCard key={a.tipo_alerta} label={`${meta.emoji} ${meta.nome}`}
              value={`${a.qtd} clientes`} delta={fmtBRL(a.valor_total)} deltaDir="flat" variant={meta.variant} />
          );
        })}
      </div>
      <div className="text-xs text-gray-500 space-y-0.5 mb-4">
        {data.alertas.map((a) => {
          const meta = ALERT_META[a.tipo_alerta];
          return meta ? <div key={a.tipo_alerta}><b>{meta.emoji} {meta.nome}:</b> {meta.desc}</div> : null;
        })}
      </div>

      <SectionTitle>Detalhe do Alerta — Clientes para Acionar</SectionTitle>
      <div className="w-80 mb-4">
        <Select label="Tipo de alerta" value={tipoAtivo} onChange={setTipo}
          options={data.alertas.map((a) => {
            const m = ALERT_META[a.tipo_alerta];
            return { value: a.tipo_alerta, label: m ? `${m.emoji} ${m.nome}` : a.tipo_alerta };
          })} />
      </div>

      {det.isLoading ? <Spinner label="Carregando clientes do alerta..." /> : det.error ? (
        <ErrorBox message={(det.error as Error).message} />
      ) : det.data ? (
        det.data.rows.length > 0 ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <KpiCard label={ALERT_META[tipoAtivo]?.nome ?? tipoAtivo}
                value={`${det.data.qtd} cliente${det.data.qtd !== 1 ? "s" : ""}`}
                variant={ALERT_META[tipoAtivo]?.variant ?? ""} />
              <KpiCard label="Faturamento do grupo" value={fmtBRL(det.data.faturamento)} />
              <KpiCard label="Ticket médio" value={fmtBRL(det.data.ticket)} />
            </div>
            <DataTable columns={detCols} rows={det.data.rows} />
          </>
        ) : (
          <InfoBox>Nenhum cliente neste alerta com os filtros atuais.</InfoBox>
        )
      ) : null}
    </div>
  );
}
