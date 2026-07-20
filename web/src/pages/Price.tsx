import { Fragment, useEffect, useState } from "react";
import { PageHeader } from "../components/layout";
import { KpiCard, Card, Select, Spinner, ErrorBox, InfoBox } from "../components/ui";
import {
  usePriceMeses,
  usePrice,
  usePriceUf,
  useSalvarPriceCusto,
  type PriceRow,
} from "../lib/api";

const BRL0 = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const BRL2 = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const NUM = new Intl.NumberFormat("pt-BR");
const fmtPct = (v: number | null | undefined) => (v == null ? "-" : `${v.toFixed(1)}%`);

type EditKey =
  | "custo_peca" | "pct_ads" | "pct_comissao"
  | "pct_credito_icms" | "pct_credito_ipi"
  | "pct_pis" | "pct_cofins" | "pct_irpj" | "pct_csll"
  | "mao_obra_unit" | "pct_custo_fixo" | "pct_outras";
type Edits = Partial<Record<EditKey, number>>;

const EDIT_FIELDS: EditKey[] = [
  "custo_peca", "pct_ads", "pct_comissao",
  "pct_credito_icms", "pct_credito_ipi",
  "pct_pis", "pct_cofins", "pct_irpj", "pct_csll",
  "mao_obra_unit", "pct_custo_fixo", "pct_outras",
];

const rowKey = (r: { item_code: string; canal: string }) => `${r.item_code}|${r.canal}`;

function calcMargem(r: PriceRow, e: Edits) {
  const fat = r.faturamento;
  const qtd = r.quantidade;
  const custoUnit = e.custo_peca ?? r.custo_peca ?? 0;
  const credito = (fat * ((e.pct_credito_icms ?? r.pct_credito_icms ?? 0)
                        + (e.pct_credito_ipi ?? r.pct_credito_ipi ?? 0))) / 100;
  const impostoNota = Math.max(r.imposto_icms + r.imposto_ipi - credito, 0);
  const maoObra = (e.mao_obra_unit ?? r.mao_obra_unit ?? 0) * qtd;
  const despesas =
    (fat * ((e.pct_ads ?? r.pct_ads ?? 0)
          + (e.pct_comissao ?? r.pct_comissao ?? 0)
          + (e.pct_custo_fixo ?? r.pct_custo_fixo ?? 0)
          + (e.pct_outras ?? r.pct_outras ?? 0))) / 100;
  const impostoLucro =
    (fat * ((e.pct_pis ?? r.pct_pis ?? 0)
          + (e.pct_cofins ?? r.pct_cofins ?? 0)
          + (e.pct_irpj ?? r.pct_irpj ?? 0)
          + (e.pct_csll ?? r.pct_csll ?? 0))) / 100;
  const custoTotal = custoUnit * qtd + maoObra + impostoNota + despesas + impostoLucro;
  const margem = fat - custoTotal;
  return { margem, margemPct: fat ? (margem / fat) * 100 : null };
}

const CANAL_COR: Record<string, string> = {
  "Mercado Livre": "bg-yellow-50 text-yellow-800",
  "Amazon": "bg-orange-50 text-orange-700",
  "Shopee": "bg-red-50 text-red-700",
  "Distribuidor/Interno": "bg-indigo-50 text-indigo-700",
};

function NumInput({
  value, placeholder, onChange, suffix,
}: {
  value: number | undefined; placeholder: number; onChange: (v: number | undefined) => void; suffix?: string;
}) {
  return (
    <div className="inline-flex items-center gap-0.5">
      <input
        type="number"
        step="0.01"
        inputMode="decimal"
        value={value ?? ""}
        placeholder={placeholder ? String(placeholder) : "0"}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        className="w-16 rounded-md border border-gray-300 bg-white px-1.5 py-1 text-right text-[12px]
                   tabular-nums text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30
                   focus:border-[#1E1882]"
      />
      {suffix && <span className="text-[10px] text-gray-400">{suffix}</span>}
    </div>
  );
}

function UfDetail({ mes, row }: { mes: string; row: PriceRow }) {
  const { data, isLoading, error } = usePriceUf(mes, row.item_code, row.canal);
  if (isLoading) {
    return <div className="px-4 py-3 text-xs text-gray-500">Carregando detalhe por estado...</div>;
  }
  if (error) {
    return <div className="px-4 py-3 text-xs text-red-600">{(error as Error).message}</div>;
  }
  const rows = data?.rows ?? [];
  if (rows.length === 0) {
    return <div className="px-4 py-3 text-xs text-gray-500">Sem UF informada para esta linha.</div>;
  }
  return (
    <div className="px-4 py-3 bg-[#FAFAFE]">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">
        Detalhe por estado
      </div>
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 text-[10px] uppercase tracking-[0.1em] text-gray-500">
            <tr>
              <th className="px-3 py-2 text-left">UF</th>
              <th className="px-3 py-2 text-right">Qtd</th>
              <th className="px-3 py-2 text-right">Faturamento</th>
              <th className="px-3 py-2 text-right">Ticket medio</th>
              <th className="px-3 py-2 text-right">Deb. ICMS</th>
              <th className="px-3 py-2 text-right">Deb. IPI</th>
              <th className="px-3 py-2 text-right">Margem R$</th>
              <th className="px-3 py-2 text-right">Margem %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((uf) => (
              <tr key={uf.uf} className="border-t border-gray-100">
                <td className="px-3 py-2 font-medium text-gray-800">{uf.uf}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-600">{NUM.format(uf.quantidade)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-700">{BRL0.format(uf.faturamento)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-600">{BRL2.format(uf.ticket_medio)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-600">{BRL0.format(uf.imposto_icms)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-gray-600">{BRL0.format(uf.imposto_ipi)}</td>
                <td className={`px-3 py-2 text-right tabular-nums font-semibold ${uf.margem >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                  {BRL0.format(uf.margem)}
                </td>
                <td className={`px-3 py-2 text-right tabular-nums font-semibold ${(uf.margem_pct ?? 0) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                  {fmtPct(uf.margem_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Price() {
  const { data: meses } = usePriceMeses();
  const [mes, setMes] = useState<string>("");
  useEffect(() => {
    if (!mes && meses && meses.length > 0) setMes(meses[0].value);
  }, [meses, mes]);

  const { data, isLoading, error } = usePrice(mes || undefined);
  const salvar = useSalvarPriceCusto();

  const [edits, setEdits] = useState<Record<string, Edits>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  useEffect(() => { setEdits({}); }, [mes]);
  useEffect(() => { setExpanded(null); }, [mes]);

  const setField = (r: PriceRow, key: EditKey, v: number | undefined) =>
    setEdits((prev) => ({ ...prev, [rowKey(r)]: { ...prev[rowKey(r)], [key]: v } }));

  const serverVal = (r: PriceRow, key: EditKey): number => (r[key] as number) ?? 0;
  const isDirty = (r: PriceRow): boolean => {
    const e = edits[rowKey(r)];
    if (!e) return false;
    return EDIT_FIELDS.some((k) => e[k] !== undefined && e[k] !== serverVal(r, k));
  };

  const salvarLinha = (r: PriceRow) => {
    const e = edits[rowKey(r)] ?? {};
    const val = (k: EditKey) => (e[k] ?? (r[k] as number) ?? 0);
    salvar.mutate(
      {
        item_code: r.item_code, canal: r.canal, mes,
        custo_peca: val("custo_peca"),
        pct_ads: val("pct_ads"),
        pct_comissao: val("pct_comissao"),
        pct_credito_icms_ipi: null,
        pct_credito_icms: val("pct_credito_icms"),
        pct_credito_ipi: val("pct_credito_ipi"),
        pct_pis: val("pct_pis"),
        pct_cofins: val("pct_cofins"),
        pct_irpj_csll: null,
        pct_irpj: val("pct_irpj"),
        pct_csll: val("pct_csll"),
        mao_obra_unit: val("mao_obra_unit"),
        pct_custo_fixo: val("pct_custo_fixo"),
        pct_outras: val("pct_outras"),
      },
      { onSuccess: () => setEdits((prev) => { const n = { ...prev }; delete n[rowKey(r)]; return n; }) },
    );
  };

  const rows = data?.rows ?? [];

  const [canalFiltro, setCanalFiltro] = useState<string>("");
  const [produtoFiltro, setProdutoFiltro] = useState<string>("");
  const canaisDisponiveis = Array.from(new Set(rows.map((r) => r.canal))).sort();

  const rowsFiltradas = rows.filter((r) => {
    if (canalFiltro && r.canal !== canalFiltro) return false;
    if (produtoFiltro) {
      const alvo = produtoFiltro.trim().toLowerCase();
      const bate = r.item_name.toLowerCase().includes(alvo) || r.item_code.toLowerCase().includes(alvo);
      if (!bate) return false;
    }
    return true;
  });

  const totais = (() => {
    const fat = rowsFiltradas.reduce((s, r) => s + r.faturamento, 0);
    const margem = rowsFiltradas.reduce((s, r) => s + r.margem, 0);
    return { faturamento: fat, margem, margem_pct: fat ? (margem / fat) * 100 : null, n_itens: rowsFiltradas.length };
  })();

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader
        title="PRICE"
        subtitle="Lucro liquido e margem por produto e canal de venda. Do preco de venda ao que sobra, item a item."
        sources={[{ name: "ERP (faturamento + impostos + custo)", active: true }]}
      />

      <InfoBox>
        <strong>Base do ERP:</strong> produto, canal, quantidade, faturamento, ticket medio,
        ICMS, IPI e custo de explosao do item. <strong>Colunas manuais</strong> (Ads,
        comissao, creditos, PIS/COFINS, IRPJ/CSLL, mao de obra, custo fixo e outras)
        seguem editaveis por produto x canal x mes.
      </InfoBox>

      <div className="flex items-end gap-3 mt-5 mb-4 flex-wrap">
        <Select
          label="Mes"
          value={mes}
          onChange={setMes}
          options={meses ?? []}
        />
        <Select
          label="Canal"
          value={canalFiltro}
          onChange={setCanalFiltro}
          options={[{ value: "", label: "Todos" }, ...canaisDisponiveis.map((c) => ({ value: c, label: c }))]}
        />
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-gray-500">Produto</span>
          <input
            type="text"
            value={produtoFiltro}
            onChange={(e) => setProdutoFiltro(e.target.value)}
            placeholder="Nome ou codigo do item"
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 w-56
                       focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882]"
          />
        </label>
      </div>

      {isLoading && <Spinner label="Carregando margem..." />}
      {error && <ErrorBox message={(error as Error).message} />}

      {data && !data.empty && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
            <KpiCard label="Faturamento" value={BRL0.format(totais?.faturamento ?? 0)} />
            <KpiCard
              label="Margem (liquida)"
              value={BRL0.format(totais?.margem ?? 0)}
              variant={(totais?.margem ?? 0) >= 0 ? "success" : "danger"}
            />
            <KpiCard
              label="Margem %"
              value={fmtPct(totais?.margem_pct ?? null)}
              variant={(totais?.margem_pct ?? 0) >= 0 ? "success" : "danger"}
            />
          </div>

          {rowsFiltradas.length === 0 ? (
            <InfoBox>Nenhum item bate com os filtros de canal/produto selecionados.</InfoBox>
          ) : (
          <Card className="!p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-[#F8F9FE] text-[10px] uppercase tracking-[0.1em] text-gray-500">
                    <th className="px-3 py-3 text-left font-medium sticky left-0 bg-[#F8F9FE] z-10">Produto</th>
                    <th className="px-3 py-3 text-left font-medium">Canal</th>
                    <th className="px-3 py-3 text-right font-medium">Qtd</th>
                    <th className="px-3 py-3 text-right font-medium">Faturamento</th>
                    <th className="px-3 py-3 text-right font-medium">Ticket medio</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">Custo/un</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">Ads</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">Comissao</th>
                    <th className="px-3 py-3 text-right font-medium">Deb. ICMS</th>
                    <th className="px-3 py-3 text-right font-medium">Deb. IPI</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">Cred. ICMS</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">Cred. IPI</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">PIS</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">COFINS</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">IRPJ</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">CSLL</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">M. obra</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">C. fixo</th>
                    <th className="px-3 py-3 text-right font-medium bg-[#FFFDF5]">Outras</th>
                    <th className="px-3 py-3 text-right font-medium">Margem R$</th>
                    <th className="px-3 py-3 text-right font-medium">Margem %</th>
                    <th className="px-3 py-3 text-right font-medium"> </th>
                  </tr>
                </thead>
                <tbody>
                  {rowsFiltradas.map((r) => {
                    const e = edits[rowKey(r)] ?? {};
                    const { margem, margemPct } = calcMargem(r, e);
                    const dirty = isDirty(r);
                    const canalCls = CANAL_COR[r.canal] ?? "bg-gray-100 text-gray-600";
                    const key = rowKey(r);
                    const isExpanded = expanded === key;
                    return (
                      <Fragment key={key}>
                      <tr className="border-b border-[#F5F5FA] hover:bg-[#FAFAFE]">
                        <td className="px-3 py-2.5 text-left sticky left-0 bg-white z-10">
                          <div className="font-medium text-gray-800 leading-tight">{r.item_name}</div>
                          <div className="text-[10.5px] text-gray-400">{r.item_code}</div>
                        </td>
                        <td className="px-3 py-2.5 text-left">
                          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10.5px] font-medium ${canalCls}`}>
                            {r.canal}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-gray-600">{NUM.format(r.quantidade)}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums font-medium text-gray-800">{BRL0.format(r.faturamento)}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-gray-600">{BRL2.format(r.ticket_medio)}</td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          {r.custo_travado_erp ? (
                            <span
                              title="Vem do custo de explosao do ERP (YVALITMVIN) — nao editavel"
                              className="inline-flex items-center gap-1 text-[12px] tabular-nums text-gray-600"
                            >
                              {BRL2.format(r.custo_peca)}
                              <span className="text-[9px] uppercase tracking-wide text-gray-400">ERP</span>
                            </span>
                          ) : (
                            <NumInput value={e.custo_peca} placeholder={r.custo_peca} onChange={(v) => setField(r, "custo_peca", v)} />
                          )}
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_ads} placeholder={r.pct_ads} onChange={(v) => setField(r, "pct_ads", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_comissao} placeholder={r.pct_comissao} onChange={(v) => setField(r, "pct_comissao", v)} suffix="%" />
                        </td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">{BRL0.format(r.imposto_icms)}</td>
                        <td className="px-3 py-2.5 text-right tabular-nums text-gray-500">{BRL0.format(r.imposto_ipi)}</td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_credito_icms} placeholder={r.pct_credito_icms} onChange={(v) => setField(r, "pct_credito_icms", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_credito_ipi} placeholder={r.pct_credito_ipi} onChange={(v) => setField(r, "pct_credito_ipi", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_pis} placeholder={r.pct_pis} onChange={(v) => setField(r, "pct_pis", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_cofins} placeholder={r.pct_cofins} onChange={(v) => setField(r, "pct_cofins", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_irpj} placeholder={r.pct_irpj} onChange={(v) => setField(r, "pct_irpj", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_csll} placeholder={r.pct_csll} onChange={(v) => setField(r, "pct_csll", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.mao_obra_unit} placeholder={r.mao_obra_unit} onChange={(v) => setField(r, "mao_obra_unit", v)} />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_custo_fixo} placeholder={r.pct_custo_fixo} onChange={(v) => setField(r, "pct_custo_fixo", v)} suffix="%" />
                        </td>
                        <td className="px-2 py-2 text-right bg-[#FFFDF5]">
                          <NumInput value={e.pct_outras} placeholder={r.pct_outras} onChange={(v) => setField(r, "pct_outras", v)} suffix="%" />
                        </td>
                        <td className={`px-3 py-2.5 text-right tabular-nums font-semibold ${margem >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                          {BRL0.format(margem)}
                        </td>
                        <td className={`px-3 py-2.5 text-right tabular-nums font-semibold ${(margemPct ?? 0) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                          {fmtPct(margemPct)}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <button
                            type="button"
                            onClick={() => setExpanded(isExpanded ? null : key)}
                            className="mr-2 rounded-md border border-gray-200 bg-white px-2 py-1 text-[11px] font-semibold text-[#1E1882] hover:bg-gray-50"
                          >
                            UF
                          </button>
                          {dirty && (
                            <button
                              onClick={() => salvarLinha(r)}
                              disabled={salvar.isPending}
                              className="rounded-md bg-[#1E1882] text-white px-2.5 py-1 text-[11px] font-semibold
                                         hover:bg-[#2C28A8] disabled:opacity-50 transition-colors"
                            >
                              {salvar.isPending ? "..." : "Salvar"}
                            </button>
                          )}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr className="border-b border-[#ECECF5]">
                          <td colSpan={22} className="p-0">
                            <UfDetail mes={mes} row={r} />
                          </td>
                        </tr>
                      )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
          )}

          <p className="text-[11px] text-gray-400 mt-3 leading-relaxed">
            Formula provisoria: margem = faturamento - custo das pecas - mao de obra
            - impostos da nota liquidos dos creditos - Ads/comissao/outras/custo fixo
            - PIS/COFINS/IRPJ/CSLL. As colunas em amarelo sao manuais e ficam salvas por produto x canal x mes.
          </p>
        </>
      )}

      {data && data.empty && (
        <InfoBox>Sem faturamento no mes selecionado.</InfoBox>
      )}
    </div>
  );
}
