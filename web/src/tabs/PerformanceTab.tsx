import { useState } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, ReferenceArea, Cell, LabelList,
} from "recharts";
import { useMeses, usePerformance, type PerformanceVendedor, type PerformanceData } from "../lib/api";
import { fmtBRL } from "../lib/format";
import { SectionTitle, Select, Spinner, ErrorBox, InfoBox, Card, Caption } from "../components/ui";

const QUAD_COLOR: Record<string, string> = {
  "Alta Performance": "#10B981",
  "Futuro Talento": "#3B82F6",
  "Esforço Ineficiente": "#D97706",
  "Baixa Entrega": "#DC2626",
};

export default function PerformanceTab() {
  const meses = useMeses();
  const [mes, setMes] = useState("");
  const mesAtivo = mes || meses.data?.[0]?.value || "";
  const perf = usePerformance(mesAtivo || undefined);

  return (
    <div className="flex flex-col gap-4">
      <SectionTitle>Matriz de Performance — Esforço x Resultado</SectionTitle>
      <Caption>
        Esforço (CRM: ligações, reuniões, propostas, follow-ups, atividades, oportunidades criadas, ciclo) x
        Resultado (CRM + ERP: receita realizada e contratada, meta atingida, pipeline gerado, conversão, ticket).
        Cada indicador é normalizado de 0 a 100 dentro do próprio grupo do mês — o melhor da equipe vira 100, o
        pior vira 0. Não é uma nota absoluta, é a posição relativa naquele mês.
      </Caption>

      <div className="w-64">
        <Select label="Mês de referência" value={mesAtivo} onChange={setMes} options={meses.data ?? []} />
      </div>

      {perf.isLoading ? (
        <Spinner />
      ) : perf.error ? (
        <ErrorBox message={(perf.error as Error).message} />
      ) : !perf.data || perf.data.vazio ? (
        <InfoBox>Sem vendedores com meta cadastrada no Pipedrive para este mês.</InfoBox>
      ) : (
        <PerformanceChart data={perf.data} />
      )}
    </div>
  );
}

function PerformanceChart({ data }: { data: PerformanceData }) {
  return (
    <Card>
      <ResponsiveContainer width="100%" height={500}>
        <ScatterChart margin={{ top: 30, right: 40, bottom: 30, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#EEEEF4" />

          {/* Fundo tingido de cada quadrante + rótulo (mesmas cores da legenda) */}
          <ReferenceArea x1={50} x2={100} y1={50} y2={100} fill={QUAD_COLOR["Alta Performance"]} fillOpacity={0.06}
            label={{ value: "ALTA PERFORMANCE", position: "insideTopRight", fill: QUAD_COLOR["Alta Performance"], fontSize: 11, fontWeight: 700 }} />
          <ReferenceArea x1={0} x2={50} y1={50} y2={100} fill={QUAD_COLOR["Futuro Talento"]} fillOpacity={0.06}
            label={{ value: "FUTURO TALENTO", position: "insideTopLeft", fill: QUAD_COLOR["Futuro Talento"], fontSize: 11, fontWeight: 700 }} />
          <ReferenceArea x1={50} x2={100} y1={0} y2={50} fill={QUAD_COLOR["Esforço Ineficiente"]} fillOpacity={0.06}
            label={{ value: "ESFORÇO INEFICIENTE", position: "insideBottomRight", fill: QUAD_COLOR["Esforço Ineficiente"], fontSize: 11, fontWeight: 700 }} />
          <ReferenceArea x1={0} x2={50} y1={0} y2={50} fill={QUAD_COLOR["Baixa Entrega"]} fillOpacity={0.06}
            label={{ value: "BAIXA ENTREGA", position: "insideBottomLeft", fill: QUAD_COLOR["Baixa Entrega"], fontSize: 11, fontWeight: 700 }} />

          <ReferenceLine x={50} stroke="#C9C9D4" />
          <ReferenceLine y={50} stroke="#C9C9D4" />

          <XAxis type="number" dataKey="esforco_score" domain={[0, 100]} name="Esforço"
            tick={{ fontSize: 11, fill: "#6B7280" }}
            label={{ value: "ESFORÇO →", position: "insideBottom", offset: -20, fill: "#6B7280", fontSize: 12, fontWeight: 600 }} />
          <YAxis type="number" dataKey="resultado_score" domain={[0, 100]} name="Resultado"
            tick={{ fontSize: 11, fill: "#6B7280" }}
            label={{ value: "RESULTADO ↑", angle: -90, position: "insideLeft", fill: "#6B7280", fontSize: 12, fontWeight: 600 }} />
          <ZAxis range={[260, 260]} />

          <Tooltip content={<PerformanceTooltip />} />

          <Scatter data={data.vendedores} shape="circle">
            {data.vendedores.map((v, i) => (
              <Cell key={i} fill={QUAD_COLOR[v.quadrante] ?? "#6B7280"} />
            ))}
            <LabelList dataKey="vendedor" position="top" offset={10} style={{ fontSize: 11.5, fill: "#15151F", fontWeight: 600 }} />
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      <div className="flex flex-wrap gap-4 mt-2 justify-center">
        {Object.entries(QUAD_COLOR).map(([nome, cor]) => (
          <div key={nome} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: cor }} />
            {nome}
          </div>
        ))}
      </div>
    </Card>
  );
}

function PerformanceTooltip({ active, payload }: { active?: boolean; payload?: { payload: PerformanceVendedor }[] }) {
  if (!active || !payload || !payload[0]) return null;
  const v = payload[0].payload;
  const d = v.detalhe;
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-lg p-3 text-xs" style={{ minWidth: 240 }}>
      <div className="font-bold text-sm text-gray-900 mb-0.5">{v.vendedor}</div>
      <div className="text-gray-500 mb-2">
        {v.quadrante} · Esforço {v.esforco_score} · Resultado {v.resultado_score}
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-gray-700">
        <span>Ligações <b>{d.ligacoes}</b></span>
        <span>Reuniões <b>{d.reunioes}</b></span>
        <span>Propostas <b>{d.propostas}</b></span>
        <span>Follow-ups <b>{d.followups}</b></span>
        <span>Atividades <b>{d.atividades_registradas}</b></span>
        <span>Oportunidades <b>{d.oportunidades_criadas}</b></span>
        <span>Ciclo médio <b>{d.ciclo_medio_dias != null ? `${d.ciclo_medio_dias}d` : "—"}</b></span>
        <span>Conversão <b>{d.conversao_pct}%</b></span>
      </div>
      <hr className="my-2 border-gray-100" />
      <div className="flex flex-col gap-1 text-gray-700">
        <span>Receita realizada (ERP) <b>{fmtBRL(d.receita_realizada)}</b></span>
        <span>Receita contratada (CRM) <b>{fmtBRL(d.receita_contratada)}</b></span>
        <span>Meta atingida <b>{d.meta_atingida_pct}%</b> {d.meta != null && <>(meta {fmtBRL(d.meta)})</>}</span>
        <span>Pipeline gerado <b>{fmtBRL(d.pipeline_gerado)}</b></span>
        <span>Ticket médio <b>{fmtBRL(d.ticket_medio)}</b></span>
      </div>
    </div>
  );
}
