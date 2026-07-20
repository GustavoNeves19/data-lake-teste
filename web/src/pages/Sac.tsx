import { useState } from "react";
import type { ReactNode } from "react";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, ReferenceLine,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { PageHeader, Tabs } from "../components/layout";
import {
  KpiCard, Caption, Card, ChartTitle, Spinner, ErrorBox, InfoBox,
} from "../components/ui";
import { fmtNum } from "../lib/format";
import { getVisiblePageTabs } from "../lib/accessCatalog";
import { useAuth } from "../lib/auth";
import type { Variant } from "../theme";
import {
  useSacAtendimentos, useSacSla, useSacChamadas, useSacChat,
  type SacAtendimentos, type SacSla, type SacChamadas, type SacChat,
} from "../lib/api";

// Formatter de tooltip do Recharts para contagens (param largo p/ casar com ValueType).
const tipNum = (v: unknown): string => fmtNum(Number(v));

// "YYYY-MM-DD..." -> "YYYY-MM" para rótulos de eixo.
const mesLabel = (m: string) => m.slice(0, 7);

// Cores dos status da pizza de atendimentos.
const STATUS_COR: Record<string, string> = {
  won: "#10B981",
  lost: "#DC2626",
  open: "#F59E0B",
};
const STATUS_FALLBACK = "#6B7280";

// Cores dos sentimentos das chamadas.
const SENTIMENTO_COR: Record<string, string> = {
  POSITIVE: "#10B981",
  NEUTRAL: "#9CA3AF",
  NEGATIVE: "#DC2626",
  UNAVAILABLE: "#C9C9D4",
};
const SENTIMENTO_FALLBACK = "#6B7280";

// Cores das direções das chamadas.
const DIRECAO_COR: Record<string, string> = {
  INBOUND: "#1E1882",
  OUTBOUND: "#4844C8",
};
const DIRECAO_FALLBACK = "#6B7280";

export default function Sac() {
  const { user } = useAuth();
  const [tab, setTab] = useState("atendimentos");
  const tabs = getVisiblePageTabs("/sac", user);
  const tabAtiva = tabs.some((t) => t.id === tab) ? tab : tabs[0]?.id;

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader
        title="SAC e Assistência Técnica"
        subtitle="Atendimentos, SLA e as conversas do time com o cliente."
        sources={[{ name: "CRM + GoTo + Umbler", active: true }]}
      />

      {tabs.length === 0 ? (
        <InfoBox>Nenhuma aba de SAC está habilitada para o seu usuário.</InfoBox>
      ) : (
        <>
          <Tabs tabs={tabs} active={tabAtiva} onChange={setTab} />

          {tabAtiva === "atendimentos" && <AtendimentosTab />}
          {tabAtiva === "sla" && <SlaTab />}
          {tabAtiva === "chamadas" && <ChamadasTab />}
          {tabAtiva === "chat" && <ChatTab />}
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

// Variante do wrapper para respostas sem o campo `empty` (ex.: SLA).
function LoaderNoEmpty<T>({
  isLoading, error, data, children,
}: {
  isLoading: boolean;
  error: unknown;
  data: T | undefined;
  children: (d: T) => ReactNode;
}) {
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox message={(error as Error).message} />;
  if (!data) return <InfoBox>Sem dados no período.</InfoBox>;
  return <>{children(data)}</>;
}

// ── Aba Atendimentos ──────────────────────────────────────────
function AtendimentosTab() {
  const q = useSacAtendimentos();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <AtendimentosContent data={d} />}
    </Loader>
  );
}

function AtendimentosContent({ data }: { data: SacAtendimentos }) {
  const k = data.kpis;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total Atendimentos" value={fmtNum(k.total_atendimentos)} />
        <KpiCard label="Resolvidos" value={fmtNum(k.resolvidos)} variant="success" />
        <KpiCard label="Taxa Resolução" value={`${fmtNum(k.taxa_resolucao_pct, 1)}%`} />
        <KpiCard label="TMR Médio" value={`${fmtNum(k.tmr_medio_h, 0)}h`} />
      </div>

      <Card>
        <ChartTitle>Volume por Mês</ChartTitle>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart
            data={data.por_mes.map((m) => ({ ...m, mes: mesLabel(m.mes) }))}
            margin={{ top: 12, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipNum} />
            <Bar dataKey="qtd" name="Atendimentos" fill="#1E1882" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <ChartTitle>Atendimentos por Status</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={data.por_status}
                dataKey="qtd"
                nameKey="status"
                cx="50%"
                cy="50%"
                outerRadius={110}
                isAnimationActive={false}
              >
                {data.por_status.map((s) => (
                  <Cell key={s.status} fill={STATUS_COR[s.status] ?? STATUS_FALLBACK} />
                ))}
              </Pie>
              <Tooltip formatter={tipNum} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <ChartTitle>Atendimentos por Pipeline</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={data.por_pipeline} margin={{ top: 12, right: 16, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
              <XAxis dataKey="rotulo" tick={{ fontSize: 11, fill: "#6B7280" }} />
              <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
              <Tooltip formatter={tipNum} />
              <Bar dataKey="qtd" name="Atendimentos" fill="#4844C8" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}

// ── Aba SLA ───────────────────────────────────────────────────
function SlaTab() {
  const q = useSacSla();
  return (
    <LoaderNoEmpty isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <SlaContent data={d} />}
    </LoaderNoEmpty>
  );
}

// Variante do TMR do último mês pela régua de SLA.
function tmrVariant(h: number): Variant {
  if (h <= 48) return "success";
  if (h <= 96) return "warning";
  return "danger";
}

function SlaContent({ data }: { data: SacSla }) {
  const k = data.kpis;
  const primeiraResp =
    k.t_primeira_resposta_mediana_min == null
      ? "—"
      : `${fmtNum(k.t_primeira_resposta_mediana_min, 0)} min`;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <KpiCard
          label="TMR Último Mês"
          value={`${fmtNum(k.tmr_resolucao_ultimo_mes_h, 0)}h`}
          variant={tmrVariant(k.tmr_resolucao_ultimo_mes_h)}
        />
        <KpiCard label="TMR Médio Geral" value={`${fmtNum(k.tmr_resolucao_medio_h, 0)}h`} />
        <KpiCard label="1ª Resposta (mediana)" value={primeiraResp} />
      </div>

      <Card>
        <ChartTitle>TMR de Resolução por Mês</ChartTitle>
        <ResponsiveContainer width="100%" height={340}>
          <LineChart
            data={data.tmr_resolucao_por_mes.map((m) => ({ ...m, mes: mesLabel(m.mes) }))}
            margin={{ top: 12, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipNum} />
            <ReferenceLine
              y={data.meta_h}
              stroke="#DC2626"
              strokeDasharray="6 4"
              label={{ value: `meta ${data.meta_h}h`, position: "right", fill: "#DC2626", fontSize: 11 }}
            />
            <Line
              type="monotone" dataKey="tmr_horas" name="TMR (h)"
              stroke="#1E1882" strokeWidth={2} dot={false} isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card>
        <ChartTitle>Tempo de 1ª Resposta (mediana, min)</ChartTitle>
        <ResponsiveContainer width="100%" height={340}>
          <LineChart
            data={data.primeira_resposta_por_mes.map((m) => ({ ...m, mes: mesLabel(m.mes) }))}
            margin={{ top: 12, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="mes" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipNum} />
            <Line
              type="monotone" dataKey="mediana_min" name="Mediana (min)"
              stroke="#10B981" strokeWidth={2} dot={false} isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}

// ── Aba Chamadas ──────────────────────────────────────────────
function ChamadasTab() {
  const q = useSacChamadas();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <ChamadasContent data={d} />}
    </Loader>
  );
}

function ChamadasContent({ data }: { data: SacChamadas }) {
  const k = data.kpis;
  const { de, ate, aviso } = data.janela;
  return (
    <div className="flex flex-col gap-5">
      <Caption>
        {aviso} · Período: {de ?? "—"} a {ate ?? "—"}
      </Caption>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <KpiCard label="Total Chamadas" value={fmtNum(k.total_chamadas)} />
        <KpiCard label="Minutos Total" value={fmtNum(k.minutos_total)} />
        <KpiCard label="Duração Média" value={`${fmtNum(k.duracao_media_min, 1)} min`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <ChartTitle>Chamadas por Direção</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={data.por_direcao}
                dataKey="qtd"
                nameKey="direcao"
                cx="50%"
                cy="50%"
                outerRadius={110}
                isAnimationActive={false}
              >
                {data.por_direcao.map((d) => (
                  <Cell key={d.direcao} fill={DIRECAO_COR[d.direcao] ?? DIRECAO_FALLBACK} />
                ))}
              </Pie>
              <Tooltip formatter={tipNum} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <ChartTitle>Chamadas por Sentimento</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={data.por_sentimento}
                dataKey="qtd"
                nameKey="sentimento"
                cx="50%"
                cy="50%"
                outerRadius={110}
                isAnimationActive={false}
              >
                {data.por_sentimento.map((s) => (
                  <Cell key={s.sentimento} fill={SENTIMENTO_COR[s.sentimento] ?? SENTIMENTO_FALLBACK} />
                ))}
              </Pie>
              <Tooltip formatter={tipNum} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>
    </div>
  );
}

// ── Aba Chat ──────────────────────────────────────────────────
function ChatTab() {
  const q = useSacChat();
  return (
    <Loader isLoading={q.isLoading} error={q.error} data={q.data}>
      {(d) => <ChatContent data={d} />}
    </Loader>
  );
}

function ChatContent({ data }: { data: SacChat }) {
  const k = data.kpis;
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Conversas SAC" value={fmtNum(k.total_conversas_sac)} />
        <KpiCard label="Canais" value={fmtNum(k.canais)} />
      </div>

      <Card>
        <ChartTitle>Conversas por Canal</ChartTitle>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={data.por_canal} margin={{ top: 12, right: 16, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
            <XAxis dataKey="canal" tick={{ fontSize: 11, fill: "#6B7280" }} />
            <YAxis tickFormatter={(v) => fmtNum(v)} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
            <Tooltip formatter={tipNum} />
            <Bar dataKey="conversas" name="Conversas" fill="#1E1882" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}
