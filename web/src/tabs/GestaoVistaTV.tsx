import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useGestaoVista, type GestaoVistaData, type GvPipelineStats, type GvEngReversa } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtBRL, fmtNum } from "../lib/format";

// ── helpers ───────────────────────────────────────────────────
function corPct(p: number): string {
  return p >= 0.9 ? "#34D399" : p >= 0.5 ? "#FBBF24" : "#F87171";
}
function brlK(v: number): string {
  const a = Math.abs(v);
  if (a >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (a >= 1_000) return `R$ ${Math.round(v / 1_000)}k`;
  return `R$ ${Math.round(v)}`;
}

const MUTED = "rgba(255,255,255,0.58)";
const TRACK = "rgba(255,255,255,0.12)";

function useRelogio(): string {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ── card base (dark) ──────────────────────────────────────────
function Card({ n, title, children, style }: { n: number; title: string; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.055)", border: "1px solid rgba(255,255,255,0.10)",
        borderRadius: 16, padding: "clamp(12px,1.1vw,20px)", minHeight: 0, overflow: "hidden",
        display: "flex", flexDirection: "column", ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 10, flexShrink: 0 }}>
        <span style={{
          width: 20, height: 20, borderRadius: "50%", background: "rgba(255,255,255,0.12)",
          color: "#C9A45A", display: "inline-flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, fontWeight: 700, flexShrink: 0,
        }}>{n}</span>
        <span style={{ fontSize: "clamp(10px,0.82vw,13px)", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".05em", color: MUTED }}>
          {title}
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>{children}</div>
    </div>
  );
}

function Barra({ w, cor }: { w: number; cor: string }) {
  return (
    <div style={{ height: "clamp(6px,0.55vw,10px)", borderRadius: 999, background: TRACK, overflow: "hidden" }}>
      <div style={{ width: `${Math.max(0, Math.min(w, 100))}%`, height: "100%", background: cor, borderRadius: 999 }} />
    </div>
  );
}

// linha nome + valor + barra (rankings, venda, pipeline, atividades)
function LinhaBarra({ nome, right, rightCor, w, cor }: { nome: string; right: string; rightCor?: string; w: number; cor: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: "clamp(11px,0.92vw,15px)", marginBottom: 4 }}>
        <span style={{ color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{nome}</span>
        <span style={{ color: rightCor ?? MUTED, fontWeight: 700, whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums" }}>{right}</span>
      </div>
      <Barra w={w} cor={cor} />
    </div>
  );
}

function ListaVazia({ children }: { children: React.ReactNode }) {
  return <div style={{ color: MUTED, fontSize: "clamp(11px,0.9vw,14px)", display: "grid", placeItems: "center", height: "100%" }}>{children}</div>;
}

// gap padrão entre linhas de uma lista (encaixe fluido)
const listaStyle: React.CSSProperties = { display: "flex", flexDirection: "column", gap: "clamp(6px,0.7vw,12px)", height: "100%", justifyContent: "space-evenly" };

// ── blocos ────────────────────────────────────────────────────
function Hero({ d }: { d: GestaoVistaData }) {
  const pct = d.pct_meta;
  const cor = corPct(pct);
  const clamped = Math.max(0, Math.min(pct, 1));
  const arc = "M18,84 A64,64 0 0 1 146,84";
  const canais = [
    { label: "Hospitalar", v: d.canais.FA },
    { label: "Farmácia", v: d.canais.FR },
    // SAC entrou no Hospitalar a partir de Julho/2026 — some do canal daqui pra frente.
    ...(d.mes < "2026-07-01" ? [{ label: "SAC", v: d.canais.PC }] : []),
    ...(d.canais.MKT != null ? [{ label: "Marketplace", v: d.canais.MKT }] : []),
  ];
  return (
    <Card n={1} title="% da meta da equipe" style={{ gridRow: "span 1" }}>
      <div style={{ height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "clamp(12px,1.4vw,28px)" }}>
          <svg viewBox="0 0 164 96" style={{ width: "clamp(130px,11vw,230px)", flexShrink: 0 }}>
            <path d={arc} stroke={TRACK} strokeWidth={14} strokeLinecap="round" fill="none" />
            <path d={arc} stroke={cor} strokeWidth={14} strokeLinecap="round" fill="none" strokeDasharray={`${clamped * 201.06} 201.06`} />
            <text x={82} y={80} textAnchor="middle" fontSize={40} fontWeight={700} fill="#fff">{`${Math.round(pct * 100)}%`}</text>
          </svg>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "clamp(12px,1vw,17px)" }}>
            <span style={{ color: MUTED }}>Meta <b style={{ color: "#fff" }}>{fmtBRL(d.meta)}</b></span>
            <span style={{ color: MUTED }}>Realizado <b style={{ color: "#34D399" }}>{fmtBRL(d.faturado_mes)}</b></span>
            <span style={{ color: MUTED }}>Falta <b style={{ color: cor }}>{fmtBRL(Math.max(d.falta, 0))}</b></span>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${canais.length}, 1fr)`, gap: "clamp(8px,0.8vw,16px)" }}>
          {canais.map((c) => (
            <div key={c.label} style={{ background: "rgba(255,255,255,0.05)", borderRadius: 10, padding: "clamp(8px,0.7vw,14px)" }}>
              <div style={{ fontSize: "clamp(10px,0.8vw,13px)", color: MUTED }}>{c.label}</div>
              <div style={{ fontSize: "clamp(16px,1.5vw,26px)", fontWeight: 700, marginTop: 2, fontVariantNumeric: "tabular-nums" }}>{brlK(c.v)}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function RankingPct({ n, title, itens, nota }: { n: number; title: string; itens: { vendedor: string; pct: number | null; pct_crm?: number | null }[]; nota: string }) {
  // Prioriza o % do CRM (barra + número); ERP vira só o % secundário.
  const top = [...itens].sort((a, b) => (b.pct_crm ?? 0) - (a.pct_crm ?? 0)).slice(0, 5);
  return (
    <Card n={n} title={title}>
      {top.length === 0 ? <ListaVazia>Sem meta cadastrada no Pipedrive</ListaVazia> : (
        <div style={listaStyle}>
          {top.map((r) => {
            const pctCrm = r.pct_crm ?? 0;
            const cor = corPct(pctCrm);
            return <LinhaBarra key={r.vendedor} nome={r.vendedor} right={`${Math.round(pctCrm * 100)}% · ERP ${Math.round((r.pct ?? 0) * 100)}%`} rightCor={cor} w={Math.min(pctCrm, 1) * 100} cor={cor} />;
          })}
        </div>
      )}
      <Nota>{nota}</Nota>
    </Card>
  );
}

// Ranking diário no Modo TV = remanescente (quanto falta vender hoje).
function RankingDiario({ itens, podeVerValores }: { itens: { vendedor: string; pct_hoje: number | null; falta_hoje: number | null; bateu_hoje: boolean | null; meta_diaria: number | null }[]; podeVerValores: boolean }) {
  const top = itens.slice(0, 5);
  return (
    <Card n={3} title="Ranking diário">
      {top.length === 0 ? <ListaVazia>Sem meta cadastrada no Pipedrive</ListaVazia> : (
        <div style={listaStyle}>
          {top.map((r) => {
            const semMeta = r.meta_diaria == null;
            const pct = r.pct_hoje ?? 0;
            const cor = semMeta ? "#9CA3AF" : r.bateu_hoje ? "#34D399" : pct >= 0.5 ? "#FBBF24" : "#F87171";
            return (
              <LinhaBarra key={r.vendedor} nome={r.vendedor}
                right={semMeta ? "Sem meta"
                  : r.bateu_hoje ? "✓ bateu hoje"
                  : podeVerValores ? `${Math.round(pct * 100)}% · falta ${brlK(r.falta_hoje ?? 0)}`
                  : `${Math.round(pct * 100)}%`}
                rightCor={cor}
                w={semMeta ? 0 : r.bateu_hoje ? 100 : Math.min(pct * 100, 100)}
                cor={cor} />
            );
          })}
        </div>
      )}
      <Nota>% da meta diária vendida hoje no CRM · melhor atingimento primeiro</Nota>
    </Card>
  );
}

function VendaDia({ d, podeVerValores }: { d: GestaoVistaData; podeVerValores: boolean }) {
  const itens = d.venda_necessaria_dia.slice(0, 5);
  const vmax = Math.max(1, ...d.venda_necessaria_dia.map((v) => v.venda_dia));
  return (
    <Card n={4} title="Venda necessária por dia">
      {itens.length === 0 ? <ListaVazia>Sem meta cadastrada</ListaVazia> : (
        <div style={listaStyle}>
          {itens.map((v) => (
            <LinhaBarra key={v.vendedor} nome={v.vendedor}
              right={v.batida ? "✓ batida" : podeVerValores ? `${fmtBRL(v.venda_dia)}/dia` : "em aberto"}
              rightCor={v.batida ? "#34D399" : "#C4B5FD"}
              w={v.batida ? 100 : Math.max((v.venda_dia / vmax) * 100, 4)}
              cor={v.batida ? "#34D399" : "#8B7FE8"} />
          ))}
        </div>
      )}
      <Nota>quanto cada um precisa vender por dia útil restante{podeVerValores ? "" : " · valor só para gestores"}</Nota>
    </Card>
  );
}

function Pipeline({ n, title, s }: { n: number; title: string; s: GvPipelineStats }) {
  const vazio = s.stages.length === 0 || s.stages.every((x) => x.valor === 0);
  const vmax = Math.max(1, ...s.stages.map((x) => x.valor));
  return (
    <Card n={n} title={title}>
      {vazio ? <ListaVazia>Pipedrive sem dados</ListaVazia> : (
        <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: "clamp(15px,1.4vw,24px)", fontWeight: 700, marginBottom: 8 }}>
            {brlK(s.pipe_open)} <span style={{ fontSize: "clamp(10px,0.8vw,13px)", fontWeight: 500, color: MUTED }}>em aberto{s.win_rate != null ? ` · win ${Math.round(s.win_rate * 100)}%` : ""}</span>
          </div>
          <div style={{ ...listaStyle, justifyContent: "flex-start", gap: "clamp(6px,0.7vw,12px)" }}>
            {s.stages.map((x) => (
              <LinhaBarra key={x.nome} nome={x.nome} right={brlK(x.valor)} w={Math.max((x.valor / vmax) * 100, 3)} cor="#4C8FE0" />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function EngReversa({ n, title, e }: { n: number; title: string; e: GvEngReversa }) {
  return (
    <Card n={n} title={title}>
      {e.vazio ? <ListaVazia>Sem vendedores com meta</ListaVazia> : (
        <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: "clamp(14px,1.3vw,22px)", fontWeight: 700 }}>{fmtBRL(e.meta_tot)} <span style={{ fontSize: "clamp(9px,0.75vw,12px)", fontWeight: 500, color: MUTED }}>restante do grupo</span></div>
          <div style={{ fontSize: "clamp(9px,0.75vw,12px)", color: MUTED, marginBottom: 8 }}>ticket {fmtBRL(e.ticket)} · funil pra bater a meta</div>
          <div style={{ display: "flex", flexDirection: "column", gap: "clamp(5px,0.6vw,10px)", justifyContent: "space-evenly", alignItems: "center", flex: 1 }}>
            {(e.etapas ?? []).map((et, i) => (
              <div key={i} style={{ width: "100%", display: "flex", justifyContent: "center" }}>
                <div style={{ height: "clamp(16px,1.5vw,26px)", background: et.cor, width: `${Math.max(et.largura, 22)}%`, minWidth: 70, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "0 10px", color: "#fff", fontSize: "clamp(10px,0.85vw,14px)", fontWeight: 600 }}>
                  <span>{et.label}</span><span style={{ opacity: 0.9 }}>{fmtNum(et.valor)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function Atividades({ n, title, itens, chave, nota }: {
  n: number; title: string;
  itens: { tipo?: string; vendedor?: string; concl: number; atras: number }[] | null;
  chave: "tipo" | "vendedor"; nota: string;
}) {
  if (itens === null) return <Card n={n} title={title}><ListaVazia>Atividades indisponíveis</ListaVazia></Card>;
  const top = itens.slice(0, 6);
  const vmax = Math.max(1, ...itens.map((i) => i.concl));
  const totC = itens.reduce((a, i) => a + i.concl, 0);
  const totA = itens.reduce((a, i) => a + i.atras, 0);
  const cores = ["#4C8FE0", "#2FB88A", "#C99A3A", "#9488E6", "#DD6A46", "#3FA36E"];
  return (
    <Card n={n} title={title}>
      <div style={{ fontSize: "clamp(10px,0.82vw,13px)", color: MUTED, marginBottom: 8 }}>
        <b style={{ color: "#fff" }}>{totC}</b> feitas · <b style={{ color: "#fff" }}>{totA}</b> atrasadas
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "clamp(6px,0.7vw,14px)", columnGap: "clamp(14px,1.4vw,28px)" }}>
        {top.map((it, i) => (
          <LinhaBarra key={(chave === "tipo" ? it.tipo : it.vendedor) ?? i}
            nome={(chave === "tipo" ? it.tipo : it.vendedor) ?? "—"}
            right={`${it.concl}${it.atras > 0 ? ` · ${it.atras}a` : ""}`}
            w={Math.max((it.concl / vmax) * 100, 3)} cor={cores[i % cores.length]} />
        ))}
      </div>
      <Nota>{nota}</Nota>
    </Card>
  );
}

function Nota({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: "clamp(9px,0.72vw,12px)", color: "rgba(255,255,255,0.4)", marginTop: 8, flexShrink: 0 }}>{children}</div>;
}

// ── componente principal ──────────────────────────────────────
export default function GestaoVistaTV({ view, mes, onClose }: { view: string; mes: string | undefined; onClose: () => void }) {
  const gv = useGestaoVista(view, mes, 60_000);
  const relogio = useRelogio();
  const { user } = useAuth();
  const podeVerValores = !!(user?.pode_editar_metas || user?.is_admin);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.requestFullscreen?.().catch(() => { /* ok */ });
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      if (document.fullscreenElement) document.exitFullscreen?.().catch(() => { /* noop */ });
    };
  }, [onClose]);

  const d = gv.data;
  const carga = gv.dataUpdatedAt ? new Date(gv.dataUpdatedAt).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "—";

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 9999, color: "#fff",
      background: "radial-gradient(130% 130% at 0% 0%, #0A0838 0%, #15104F 40%, #1E1882 100%)",
      display: "flex", flexDirection: "column", overflow: "hidden",
      fontFamily: 'var(--font-sans, "Inter", system-ui, sans-serif)',
    }}>
      {/* barra superior */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, padding: "clamp(10px,1vw,18px) clamp(18px,1.8vw,36px)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
          <span style={{ fontSize: "clamp(11px,0.9vw,14px)", letterSpacing: ".26em", color: "#C9A45A", fontWeight: 600, textTransform: "uppercase" }}>Nevoni 360</span>
          <span style={{ fontSize: "clamp(18px,1.7vw,30px)", fontWeight: 700 }}>Gestão à Vista</span>
          <span style={{ fontSize: "clamp(12px,1vw,17px)", color: "rgba(255,255,255,0.7)" }}>{d?.mes_label ?? "Carregando…"}</span>
          <span style={{ fontSize: "clamp(11px,0.9vw,15px)", fontWeight: 600, background: "rgba(255,255,255,0.14)", padding: "3px 12px", borderRadius: 999 }}>{view}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "clamp(18px,1.8vw,32px)", fontWeight: 700, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{relogio}</div>
            <div style={{ fontSize: "clamp(9px,0.75vw,12px)", color: MUTED, marginTop: 3 }}>Atualiza sozinho · carga {carga}</div>
          </div>
          <button type="button" onClick={onClose} aria-label="Sair do Modo TV" title="Sair (Esc)"
            style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(255,255,255,0.10)", border: "1px solid rgba(255,255,255,0.20)", color: "#fff", borderRadius: 10, padding: "8px 14px", cursor: "pointer", fontSize: "clamp(11px,0.9vw,14px)", fontWeight: 600 }}>
            <X size={16} /> Sair
          </button>
        </div>
      </header>

      {/* grid que preenche a tela — 3 faixas, todos os 10 blocos */}
      {!d ? (
        <div style={{ flex: 1, display: "grid", placeItems: "center", fontSize: 22, color: MUTED }}>Carregando o painel…</div>
      ) : (
        <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", gap: "clamp(10px,0.9vw,18px)", padding: "0 clamp(18px,1.8vw,36px) clamp(14px,1.2vw,26px)" }}>
          <div style={{ flex: 1.15, minHeight: 0, display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr 1fr", gap: "clamp(10px,0.9vw,18px)" }}>
            <Hero d={d} />
            <RankingPct n={2} title="Ranking mensal" itens={d.ranking_mensal} nota="% da meta pelos negócios ganhos no CRM (barra) · ERP = % já faturado" />
            <RankingDiario itens={d.ranking_diario} podeVerValores={podeVerValores} />
            <VendaDia d={d} podeVerValores={podeVerValores} />
          </div>
          <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "clamp(10px,0.9vw,18px)" }}>
            <Pipeline n={5} title="Pipeline — Hospitalar" s={d.pipeline_hosp} />
            <Pipeline n={6} title="Pipeline — Farmácia" s={d.pipeline_farma} />
            <EngReversa n={7} title="Eng. reversa — Hospitalar" e={d.eng_reversa_hosp} />
            <EngReversa n={8} title="Eng. reversa — Farmácia" e={d.eng_reversa_farma} />
          </div>
          <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "1fr 1fr", gap: "clamp(10px,0.9vw,18px)" }}>
            <Atividades n={9} title="Atividades por tipo" itens={d.atividades_tipo} chave="tipo" nota="ranqueado por feitas · toda a equipe" />
            <Atividades n={10} title="Atividades por vendedor" itens={d.atividades_vendedor} chave="vendedor" nota="feitas no período · atrasadas sem data no Pipedrive" />
          </div>
        </div>
      )}
    </div>
  );
}
