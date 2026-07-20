import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { useCompras } from "../lib/api";
import { fmtBRL, fmtNum, fmtCompact, tipBRL } from "../lib/format";
import {
  KpiCard, SectionTitle, Caption, Card, ChartTitle, DataTable, Spinner, ErrorBox, InfoBox,
  type Column,
} from "../components/ui";

const axisFmt = (v: number) => fmtCompact(v).replace("R$ ", "");

export default function ComprasTab() {
  const { data, isLoading, error } = useCompras();
  if (isLoading) return <Spinner />;
  if (error) return <ErrorBox message={(error as Error).message} />;
  if (!data || data.empty) return <InfoBox>Sem dados de compras.</InfoBox>;

  const k = data.kpis;
  const importChart = [...data.import_fornecedores]
    .sort((a, b) => b.valor - a.valor)
    .slice(0, 8);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <SectionTitle>Compras e Suprimentos</SectionTitle>
        <Caption>
          A Nevoni FABRICA: dois canais de suprimento alimentam a produção — compra de mercadoria
          doméstica e importação de insumos da China. A razão compra/venda funciona como margem de
          manufatura (quanto do faturamento volta como custo de suprimento).
        </Caption>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Compras Mercadoria (12m)"
          value={fmtBRL(k.compras_dom)}
          variant="warning"
        />
        <KpiCard
          label="Importação (acumulado)"
          value={fmtBRL(k.importacao_brl)}
          delta={`US$ ${fmtNum(k.importacao_usd, 0)}`}
        />
        <KpiCard
          label="Razão Compra/Venda"
          value={`${fmtNum(k.razao_compra_venda, 1)}%`}
          variant="success"
        />
        <KpiCard
          label="Concentração Import"
          value={`${fmtNum(k.concentracao_import, 1)}%`}
          delta={k.top_fornecedor_import}
          variant="danger"
        />
      </div>

      {/* Honestidade de dados: lacuna upstream em fact_purchase_order */}
      {k.compras_dom === 0 && (
        <InfoBox>
          A tabela de compras do ERP (<code>fact_purchase_order</code>) não é ingerida desde 2008,
          então as compras de mercadoria doméstica dos últimos 12 meses aparecem zeradas. É uma
          lacuna na fonte (upstream), não um erro do painel. A importação e os gráficos com dados
          continuam válidos abaixo.
        </InfoBox>
      )}

      {/* Chart 1: Vendas vs Compras por mês */}
      {data.serie.length > 0 && (
        <Card>
          <ChartTitle>Vendas vs Compras por Mês</ChartTitle>
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={data.serie} margin={{ top: 20, right: 12, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#EEF0FF" />
              <XAxis dataKey="mes_label" tick={{ fontSize: 11, fill: "#6B7280" }} />
              <YAxis tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
              <Tooltip formatter={tipBRL} />
              <Legend />
              <Bar dataKey="vendas" name="Vendas" fill="#16A34A" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="compras" name="Compras" fill="#4844C8" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Chart 2: Importação por fornecedor (horizontal, top 8) */}
      {importChart.length > 0 && (
        <Card>
          <ChartTitle>Importação por Fornecedor</ChartTitle>
          <ResponsiveContainer width="100%" height={Math.max(220, importChart.length * 42)}>
            <BarChart
              data={importChart}
              layout="vertical"
              margin={{ top: 8, right: 24, left: 8, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#EEF0FF" />
              <XAxis type="number" tickFormatter={axisFmt} tick={{ fontSize: 11, fill: "#9CA3AF" }} />
              <YAxis
                type="category"
                dataKey="fornecedor"
                width={160}
                tick={{ fontSize: 11, fill: "#6B7280" }}
              />
              <Tooltip formatter={tipBRL} />
              <Bar dataKey="valor" name="Importação" fill="#991B1B" radius={[0, 3, 3, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Tabela: Top fornecedores doméstico (12m) */}
      {data.top_fornecedores.length > 0 && (
        <Card>
          <ChartTitle>Top Fornecedores Doméstico (12m)</ChartTitle>
          <DataTable
            columns={[
              { key: "fornecedor", header: "Fornecedor" },
              { key: "ordens", header: "Ordens", align: "right", render: (r) => fmtNum(r.ordens) },
              { key: "valor", header: "Valor", align: "right", render: (r) => fmtBRL(r.valor) },
            ] as Column<typeof data.top_fornecedores[number]>[]}
            rows={data.top_fornecedores}
          />
        </Card>
      )}
    </div>
  );
}
