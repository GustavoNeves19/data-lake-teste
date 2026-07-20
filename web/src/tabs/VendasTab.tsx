import { useMemo, useState } from "react";
import { Tv, ChevronDown } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { useMeses, useVendas, useVendasPeriodo } from "../lib/api";
import VendasTV from "./VendasTV";
import { fmtBRL, fmtPct, fmtNum, fmtCompact, tipBRL } from "../lib/format";
import {
  KpiCard, SectionTitle, Caption, Card, ChartTitle, Select, DataTable, Spinner, ErrorBox, InfoBox,
  type Column,
} from "../components/ui";
import CalendarioVendas from "../components/CalendarioVendas";
import FaturamentoMensal from "../components/FaturamentoMensal";
import { ORDEM_CANAL, CANAL_COR, CANAL_VISUAL, PERIODO_CORES } from "../theme";

// Hoje e 7 dias atrás em ISO (YYYY-MM-DD), para os inputs de período exato.
const hojeISO = () => new Date().toISOString().slice(0, 10);
const seteDiasAtrasISO = () => {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
};

const axisFmt = (v: number) => fmtCompact(v).replace("R$ ", "");

export default function VendasTab() {
  const meses = useMeses();
  const [mes, setMes] = useState<string>("");
  const [incluirMarketplace, setIncluirMarketplace] = useState<boolean>(true);
  const [tvMode, setTvMode] = useState(false);

  // default = mês mais recente disponível (mês corrente), não mais travado em Maio
  const mesAtivo = useMemo(() => {
    if (mes) return mes;
    const list = meses.data ?? [];
    if (list.length === 0) return "";
    return list.reduce((a, b) => (b.value > a.value ? b : a), list[0]).value;
  }, [mes, meses.data]);

  const vendas = useVendas(mesAtivo, incluirMarketplace);

  return (
    <div>
      <SectionTitle>Dashboard Semanal de Liderança</SectionTitle>

      <div className="flex flex-wrap items-end gap-6 mb-4">
        <div className="w-64">
          <Select
            label="Mês de referência"
            value={mesAtivo}
            onChange={setMes}
            options={meses.data ?? []}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none pb-2">
          <input
            type="checkbox"
            checked={incluirMarketplace}
            onChange={(e) => setIncluirMarketplace(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-[#1E1882] focus:ring-2 focus:ring-[#1E1882]/30 cursor-pointer"
          />
          <span className="flex flex-col leading-tight">
            <span className="font-medium">Incluir Marketplace</span>
            <span className="text-[11px] text-gray-400">
              Marketplace (Mercado Livre/Shopee) no total; desligue para ticket B2B puro.
            </span>
          </span>
        </label>
        {vendas.data && !vendas.data.empty && (
          <button
            type="button"
            onClick={() => setTvMode(true)}
            title="Abrir os números essenciais em tela cheia para a TV"
            className="ml-auto inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold text-white mb-2"
            style={{ background: "#1E1882" }}
          >
            <Tv size={16} /> Modo TV
          </button>
        )}
      </div>

      {tvMode && vendas.data && !vendas.data.empty && (
        <VendasTV data={vendas.data} mes={mesAtivo} onClose={() => setTvMode(false)} />
      )}

      {meses.isLoading || vendas.isLoading ? (
        <Spinner />
      ) : vendas.error ? (
        <ErrorBox message={(vendas.error as Error).message} />
      ) : !vendas.data || vendas.data.empty ? (
        <InfoBox>Sem dados para o mês selecionado.</InfoBox>
      ) : (
        <VendasContent data={vendas.data} />
      )}

      <PeriodoExatoSection />

      <SectionTitle>Calendário de Vendas Diárias</SectionTitle>
      <CalendarioVendas mes={mesAtivo} />

      <SectionTitle>Faturamento Mensal — 3 anos</SectionTitle>
      <FaturamentoMensal />
    </div>
  );
}

// ── Período Exato (por datas De/Até) ──────────────────────────
function PeriodoExatoSection() {
  const [de, setDe] = useState<string>(seteDiasAtrasISO);
  const [ate, setAte] = useState<string>(hojeISO);

  const periodo = useVendasPeriodo(de, ate);
  const d = periodo.data;

  return (
    <>
      <SectionTitle>Vendas e Faturamento por Período Exato</SectionTitle>
      <Caption>
        Vendas = pedidos por data de emissão (order_date); Faturamento = notas por data da nota (invoice_date).
      </Caption>

      <div className="flex flex-wrap items-end gap-4 mb-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-gray-500">De</span>
          <input
            type="date"
            value={de}
            max={ate}
            onChange={(e) => setDe(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800
                       focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882] cursor-pointer"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-gray-500">Até</span>
          <input
            type="date"
            value={ate}
            min={de}
            onChange={(e) => setAte(e.target.value)}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800
                       focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882] cursor-pointer"
          />
        </label>
        {periodo.isLoading && <Spinner label="Consultando período..." />}
      </div>

      {periodo.error ? (
        <ErrorBox message={(periodo.error as Error).message} />
      ) : d ? (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard label="Vendas (pedidos)" value={fmtBRL(d.vendas_pedidos)} />
            <KpiCard label="Faturamento (notas)" value={fmtBRL(d.faturamento_notas)} variant="success" />
            <KpiCard label="Pedidos" value={fmtNum(d.pedidos)} />
            <KpiCard label="Ticket médio" value={fmtBRL(d.ticket)} />
          </div>
          <DataTable
            columns={[
              { key: "canal", header: "Canal" },
              { key: "pedidos", header: "Pedidos", align: "right", render: (r) => fmtNum(r.pedidos) },
              { key: "faturamento", header: "Faturamento", align: "right", render: (r) => fmtBRL(r.faturamento) },
            ] as Column<typeof d.por_canal[number]>[]}
            rows={d.por_canal}
          />
        </div>
      ) : null}
    </>
  );
}

function VendasContent({ data }: { data: NonNullable<ReturnType<typeof useVendas>["data"]> }) {
  const k = data.kpis;
  const [mktAberto, setMktAberto] = useState(false);

  const canalChart = data.canais.map((c) => ({
    canal: c.canal,
    [data.label_ref]: c.faturamento,
    [data.label_ant]: c.fat_ant,
    [data.label_yoy]: c.fat_yoy,
  }));

  return (
    <div className="flex flex-col gap-5">
      {/* KPIs — os 5 numa linha só em tela larga (xl), 3 no tablet, 2 no celular */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {k.projecao != null && (
          <KpiCard
            label="Projeção (esperado até hoje)"
            value={fmtBRL(k.projecao)}
            delta={fmtPct((k.faturamento / k.projecao - 1) * 100)}
            deltaDir={k.faturamento >= k.projecao ? "up" : "down"}
            variant={k.faturamento >= k.projecao ? "success" : "danger"}
          />
        )}
        <KpiCard label="Faturamento" value={fmtBRL(k.faturamento)} variant="success" />
        <KpiCard
          label="vs. mês anterior" value={fmtBRL(k.fat_ant)}
          delta={fmtPct(k.var_mom)} deltaDir={(k.var_mom ?? 0) >= 0 ? "up" : "down"}
          variant={(k.var_mom ?? 0) >= 0 ? "success" : "danger"}
        />
        {k.fat_yoy ? (
          <KpiCard
            label={`vs. ${data.label_yoy}`} value={fmtBRL(k.fat_yoy)}
            delta={fmtPct(k.var_yoy)} deltaDir={(k.var_yoy ?? 0) >= 0 ? "up" : "down"}
            variant={(k.var_yoy ?? 0) >= 0 ? "success" : "danger"}
          />
        ) : (
          <KpiCard label={`vs. ${data.label_yoy}`} value="—" />
        )}
        <KpiCard
          label="Ticket médio"
          value={fmtBRL(k.ticket)}
          delta={`${fmtNum(k.transacoes)} transações`}
          deltaDir="flat"
        />
      </div>

      {/* Canal: gráfico + cards */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <Card className="lg:col-span-3">
          <ChartTitle>Faturamento por Canal — comparativo dos 3 períodos</ChartTitle>
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={canalChart} margin={{ top: 20, right: 12, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
              <XAxis dataKey="canal" tick={{ fontSize: 12, fill: "#6B7280" }} />
              <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
              <Tooltip formatter={tipBRL} />
              <Legend />
              {[data.label_ref, data.label_ant, data.label_yoy].map((label, i) => (
                <Bar key={label} dataKey={label} fill={PERIODO_CORES[i]} radius={[3, 3, 0, 0]} isAnimationActive={false} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <div className="lg:col-span-2 flex flex-col gap-3">
          {data.canais.map((c) => {
            const vis = CANAL_VISUAL[c.canal] ?? CANAL_VISUAL.Outros;
            const temDetalhe = c.canal === "Marketplace" && data.marketplace_detalhe.length > 0;
            const aberto = temDetalhe && mktAberto;
            return (
              <div
                key={c.canal}
                className="bg-white rounded-[10px] px-4 py-3.5 shadow-[0_1px_2px_rgba(0,0,0,0.04)] border border-gray-200"
                style={{ borderLeft: `4px solid ${vis.cor}` }}
              >
                <button
                  type="button"
                  onClick={() => temDetalhe && setMktAberto((v) => !v)}
                  disabled={!temDetalhe}
                  className={`w-full text-left ${temDetalhe ? "cursor-pointer" : "cursor-default"}`}
                >
                  <div className="flex justify-between items-baseline">
                    <div className="text-[13px] font-bold text-gray-900 uppercase tracking-wide flex items-center gap-1.5">
                      <span className="text-base">{vis.emoji}</span>{c.canal}
                      {temDetalhe && (
                        <ChevronDown
                          size={14}
                          strokeWidth={2}
                          className={`text-gray-400 transition-transform ${aberto ? "rotate-180" : ""}`}
                        />
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-xl font-extrabold leading-tight" style={{ color: vis.cor }}>
                        {fmtBRL(c.faturamento)}
                      </div>
                      <div className="text-[10px] text-gray-400 mt-0.5">referência: {data.label_ref}</div>
                    </div>
                  </div>
                  <div className="flex gap-5 mt-2 text-xs text-gray-500">
                    <span>vs. mês anterior <Delta v={c.var_mom} /></span>
                    <span>vs. mesmo mês do ano passado <Delta v={c.var_yoy} /></span>
                  </div>
                  <div className="flex gap-5 mt-1 text-xs text-gray-500">
                    <span>📊 <b>{fmtNum(c.transacoes)}</b> transações</span>
                    <span>🎯 ticket <b>{fmtBRL(c.ticket)}</b></span>
                  </div>
                </button>

                {aberto && (
                  <div className="mt-3 pt-3 border-t border-gray-100 flex flex-col gap-2">
                    {data.marketplace_detalhe.map((sc) => (
                      <div key={sc.sub_canal} className="flex justify-between items-center text-xs">
                        <span className="font-medium text-gray-700">{sc.sub_canal}</span>
                        <span className="flex items-center gap-3 text-gray-500">
                          <span>{fmtNum(sc.transacoes)} transações</span>
                          <span>ticket {fmtBRL(sc.ticket)}</span>
                          <b className="text-gray-900">{fmtBRL(sc.faturamento)}</b>
                          <span className="text-gray-400">({fmtPct(sc.pct_marketplace)})</span>
                        </span>
                      </div>
                    ))}
                    <div className="text-[10px] text-gray-400 mt-1">
                      Fonte: fact_sales_order por canal do pedido (YCODVEN), mesmo mês de referência do card acima.
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Evolução 12 meses */}
      {data.evolucao.length > 0 && (
        <Card>
          <ChartTitle>Evolução Mensal por Canal — últimos 12 meses</ChartTitle>
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={data.evolucao} margin={{ top: 20, right: 12, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
              <XAxis dataKey="mes_label" tick={{ fontSize: 11, fill: "#6B7280" }} />
              <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
              <Tooltip formatter={tipBRL} />
              <Legend />
              {ORDEM_CANAL.filter((c) => c !== "Outros").map((c) => (
                <Bar key={c} dataKey={c} fill={CANAL_COR[c]} radius={[2, 2, 0, 0]} isAnimationActive={false} />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <details className="mt-3">
            <summary className="cursor-pointer text-sm text-gray-600 font-medium">📅 Detalhamento mensal (total)</summary>
            <div className="mt-3">
              <DataTable
                columns={[
                  { key: "mes_label", header: "Mês" },
                  { key: "faturamento", header: "Faturamento Total", align: "right", render: (r) => fmtBRL(r.faturamento) },
                  { key: "mom", header: "% vs. mês anterior", align: "right", render: (r) => (r.mom == null ? "—" : fmtPct(r.mom)) },
                ] as Column<typeof data.total_mensal[number]>[]}
                rows={data.total_mensal}
              />
            </div>
          </details>
        </Card>
      )}

      {/* Semanal */}
      {data.semanas.length > 0 && (
        <Card>
          <ChartTitle>Faturamento Semanal por Canal — {data.label_ref}</ChartTitle>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={data.semanas} margin={{ top: 12, right: 12, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
              <XAxis dataKey="semana_label" tick={{ fontSize: 11, fill: "#6B7280" }} />
              <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
              <Tooltip formatter={tipBRL} />
              <Legend />
              {ORDEM_CANAL.filter((c) => c !== "Outros").map((c) => (
                <Bar key={c} dataKey={c} stackId="s" fill={CANAL_COR[c]} isAnimationActive={false} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}
    </div>
  );
}

function Delta({ v }: { v: number | null }) {
  if (v == null) return <span className="text-gray-400">—</span>;
  const up = v >= 0;
  return (
    <span className={up ? "text-emerald-600 font-semibold" : "text-red-600 font-semibold"}>
      {up ? "▲" : "▼"} {Math.abs(v).toFixed(1)}%
    </span>
  );
}
