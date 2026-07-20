import { useState } from "react";
import { useVisaoGeral, type FrescorFonte, type RunResumo, type RunDetalhe } from "../lib/api";
import { PageHeader } from "../components/layout";
import { Card, SectionTitle, DataTable, Spinner, ErrorBox, type Column } from "../components/ui";
import { fmtNum } from "../lib/format";

const GRID = { display: "grid", gap: "14px", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } as const;

export default function VisaoGeral() {
  const { data, isLoading, error } = useVisaoGeral();
  const [aberto, setAberto] = useState(false);

  if (isLoading) return <div className="p-16"><Spinner label="Carregando estado das fontes…" /></div>;
  if (error) return <div className="max-w-[1440px] mx-auto px-6 py-6"><ErrorBox message={(error as Error).message} /></div>;
  if (!data) return null;

  const resumoCols: Column<RunResumo>[] = [
    { key: "fonte", header: "Fonte" },
    { key: "ultima_carga", header: "Última carga" },
    { key: "idade_txt", header: "Há" },
    { key: "cargas_hoje", header: "Cargas hoje", align: "right", render: (r) => fmtNum(r.cargas_hoje) },
  ];
  const detalheCols: Column<RunDetalhe>[] = [
    { key: "quando", header: "Quando" },
    { key: "fonte", header: "Fonte" },
    { key: "entidade", header: "Entidade" },
    { key: "status", header: "Status" },
    { key: "linhas", header: "Linhas", align: "right", render: (r) => fmtNum(r.linhas) },
    { key: "segundos", header: "Segundos", align: "right", render: (r) => `${r.segundos.toFixed(1)}s` },
  ];

  return (
    <div className="max-w-[1440px] mx-auto px-6 py-6">
      <PageHeader title={data.header.title} subtitle={data.header.subtitle} sources={data.header.sources} />

      <SectionTitle>Frescor das fontes</SectionTitle>
      <div style={GRID}>
        {data.frescor.map((f) => <FrescorCard key={f.table_id} f={f} />)}
      </div>

      <SectionTitle>Cadência programada</SectionTitle>
      <div style={GRID}>
        {data.cadencia.cards.map((c) => (
          <div key={c.titulo} className="rounded-[10px] px-3.5 py-3" style={{ background: "#F7F7FB" }}>
            <div className="text-[11px] text-[#8A8A99]">{c.titulo}</div>
            <div className="text-[15px] font-bold text-[#1E1882]">{c.valor}</div>
            <div className="text-[11px] text-[#A6A6B2]">{c.sub}</div>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-2">{data.cadencia.nota}</p>

      <SectionTitle>Histórico de execuções</SectionTitle>
      {data.erros.runs_resumo ? (
        <Aviso msg={data.erros.runs_resumo} />
      ) : (
        <DataTable columns={resumoCols} rows={data.runs_resumo} />
      )}

      <button
        onClick={() => setAberto((v) => !v)}
        className="mt-3 text-sm font-semibold text-[#1E1882] hover:underline"
      >
        {aberto ? "▾ Ocultar detalhe" : "▸ Ver as últimas 20 execuções (detalhe)"}
      </button>
      {aberto && (
        <div className="mt-3">
          {data.erros.runs_detalhe ? (
            <Aviso msg={data.erros.runs_detalhe} />
          ) : (
            <DataTable columns={detalheCols} rows={data.runs_detalhe} />
          )}
        </div>
      )}

    </div>
  );
}

function FrescorCard({ f }: { f: FrescorFonte }) {
  return (
    <Card className="!p-3.5" >
      <div style={{ borderLeft: `4px solid ${f.cor}`, paddingLeft: "12px", marginLeft: "-4px" }}>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: f.cor }} />
          <span className="text-xs font-semibold text-[#6B6B7A]">{f.rotulo}</span>
        </div>
        <div className="text-xl font-bold text-[#15151F] tabular-nums mt-1">{f.modified_brt}</div>
        <div className="text-xs font-semibold" style={{ color: f.cor }}>
          {f.idade_txt}{f.modified_utc ? " BRT" : ""}
        </div>
      </div>
    </Card>
  );
}

function Aviso({ msg }: { msg: string }) {
  return (
    <div className="rounded-lg px-4 py-3 text-sm" style={{ background: "#FEF3E2", color: "#8A5A00" }}>
      ⚠️ {msg}
    </div>
  );
}
