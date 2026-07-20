import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Pencil, Tv } from "lucide-react";
import {
  useGestaoVistaMeses, useGestaoVista, useSalvarMeta, useAtividadesPeriodo,
  type GestaoVistaData, type GvPipelineStats, type GvEngReversa,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtBRL, fmtNum } from "../lib/format";
import { Select, Spinner, ErrorBox, InfoBox } from "../components/ui";
import GestaoVistaTV from "./GestaoVistaTV";

// ── Visões ────────────────────────────────────────────────────
const VIEWS = ["Geral", "Hospitalar", "Farmácia"];

// Formato compacto curto pros heros/chips (R$ X,XM / R$ Xk / R$ X).
function brlK(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (abs >= 1_000) return `R$ ${Math.round(v / 1_000)}k`;
  return `R$ ${Math.round(v)}`;
}

// Paleta dos badges por par de cards (1-2, 3-4, 5-6, 7-8, 9-10).
const BADGE: Record<number, { bg: string; fg: string }> = {
  1: { bg: "#E1F5EE", fg: "#0F6E56" },
  2: { bg: "#E1F5EE", fg: "#0F6E56" },
  3: { bg: "#EEEDFE", fg: "#3C3489" },
  4: { bg: "#EEEDFE", fg: "#3C3489" },
  5: { bg: "#E6F1FB", fg: "#0C447C" },
  6: { bg: "#E6F1FB", fg: "#0C447C" },
  7: { bg: "#F1EFE8", fg: "#444441" },
  8: { bg: "#F1EFE8", fg: "#444441" },
  9: { bg: "#FAEEDA", fg: "#854F0B" },
  10: { bg: "#FAEEDA", fg: "#854F0B" },
};

// Paleta ciclada das barras de atividades (cards 9 e 10).
const ATIV_CORES = [
  "#185FA5", "#1D9E75", "#BA7517", "#7F77DD",
  "#D85A30", "#0F6E56", "#A33D8A", "#3C7A1E",
];

const GRUPO_CINZA = "#6B6B7A";

// SAC entrou no Hospitalar a partir deste mês — o canal SAC só aparece em meses
// ANTERIORES a esta data (auditoria); daqui pra frente some.
const SAC_FIM = "2026-07-01";

// ── Card base ─────────────────────────────────────────────────
function GvCard({
  num, title, fonte, wide = false, children,
}: {
  num: number; title: string; fonte?: string; wide?: boolean; children: React.ReactNode;
}) {
  const badge = BADGE[num];
  return (
    <div
      style={{
        gridColumn: wide ? "span 2" : undefined,
        border: "1px solid #ECECF3",
        borderRadius: 14,
        padding: "20px 22px",
        background: "#fff",
        boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <span
          style={{
            width: 22, height: 22, borderRadius: "50%",
            background: badge.bg, color: badge.fg,
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            fontSize: 12, fontWeight: 700, flexShrink: 0,
          }}
        >
          {num}
        </span>
        <span
          style={{
            fontSize: 11, fontWeight: 600, textTransform: "uppercase",
            letterSpacing: ".045em", color: GRUPO_CINZA,
          }}
        >
          {title}
        </span>
        {fonte && (
          <span
            title={`Fonte dos dados: ${fonte}`}
            style={{
              marginLeft: "auto", fontSize: 9.5, fontWeight: 700, letterSpacing: ".04em",
              color: "#5A55A8", background: "#EEEDFB", border: "1px solid #DEDCF5",
              borderRadius: 999, padding: "2px 8px", textTransform: "uppercase", flexShrink: 0,
            }}
          >
            {fonte}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

// Nota pequena no rodapé de cada card.
function Nota({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 11, color: "#9A9AA8", marginTop: 12, lineHeight: 1.4 }}>
      {children}
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────
export default function GestaoVistaTab() {
  const { user } = useAuth();
  const podeVerValores = !!(user?.pode_editar_metas || user?.is_admin);
  const [view, setView] = useState("Geral");
  const [mes, setMes] = useState<string | undefined>(undefined);
  const [tvMode, setTvMode] = useState(false);
  const [vendedorSel, setVendedorSel] = useState("");

  const meses = useGestaoVistaMeses();
  const mesAtivo = mes ?? meses.data?.[0]?.value;

  const gv = useGestaoVista(view, mesAtivo, 0, vendedorSel);

  return (
    <div className="flex flex-col gap-4">
      {/* 1) Band */}
      <div
        style={{
          background: "#1E1882", color: "#fff", borderRadius: 14,
          padding: "20px 26px", display: "flex", justifyContent: "space-between",
          alignItems: "center", gap: 16, flexWrap: "wrap",
        }}
      >
        <div style={{ fontSize: 21, fontWeight: 600 }}>Painel de Gestão à Vista</div>
        <button
          type="button"
          onClick={() => setTvMode(true)}
          title="Abrir em tela cheia para exibir na TV (atualiza sozinho)"
          style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.22)",
            color: "#fff", borderRadius: 10, padding: "8px 16px", cursor: "pointer",
            fontSize: 13, fontWeight: 600,
          }}
        >
          <Tv size={16} /> Modo TV
        </button>
      </div>

      {tvMode && (
        <GestaoVistaTV view={view} mes={mesAtivo} onClose={() => setTvMode(false)} />
      )}

      {/* 2) Controles */}
      <div className="flex flex-wrap items-end gap-6">
        <div className="flex flex-col gap-1 text-sm">
          <span className="text-xs font-medium text-gray-500">Visão</span>
          <div className="flex items-center gap-4 h-[38px]">
            {VIEWS.map((v) => (
              <label key={v} className="flex items-center gap-1.5 cursor-pointer text-sm text-gray-800">
                <input
                  type="radio"
                  name="gv-view"
                  value={v}
                  checked={view === v}
                  onChange={() => setView(v)}
                  className="accent-[#1E1882]"
                />
                {v}
              </label>
            ))}
          </div>
        </div>
        <div className="w-44">
          <Select
            label="Mês"
            value={mesAtivo ?? ""}
            onChange={setMes}
            options={meses.data ?? []}
          />
        </div>
        <div className="w-60">
          <Select
            label="Vendedor (resultado individual)"
            value={vendedorSel}
            onChange={setVendedorSel}
            options={[
              { value: "", label: "— todos —" },
              ...(gv.data?.vendedores ?? []).map((x) => ({ value: x.vendedor, label: x.vendedor })),
            ]}
          />
        </div>
      </div>

      {vendedorSel && gv.data && <VendedorResultado data={gv.data} vendedor={vendedorSel} podeVerValores={podeVerValores} />}

      {meses.isLoading || gv.isLoading ? (
        <Spinner />
      ) : gv.error ? (
        <ErrorBox message={(gv.error as Error).message} />
      ) : gv.data ? (
        <GvContent data={gv.data} />
      ) : null}
    </div>
  );
}

// ── Resultado individual do vendedor (filtro) ─────────────────
// Ranking continua em % pra todos (competição); aqui mostra o valor em R$ do
// vendedor selecionado — meta + realizado + % — como o Vinícius pediu (07/07).
function VendedorResultado({ data, vendedor, podeVerValores }: { data: GestaoVistaData; vendedor: string; podeVerValores: boolean }) {
  const vd = data.vendedores.find((x) => x.vendedor === vendedor);
  if (!vd) return null;
  const temMeta = vd.meta != null;
  const pct = vd.pct ?? 0;
  const cor = pct >= 0.85 ? "#1D9E75" : pct >= 0.5 ? "#D97706" : "#DC2626";
  return (
    <div style={{
      background: "#F8F9FE", border: "1px solid #E6E7F2", borderLeft: "5px solid #1E1882",
      borderRadius: 12, padding: "16px 22px", display: "flex", flexWrap: "wrap", gap: 36, alignItems: "center",
    }}>
      <div style={{ fontSize: 16, fontWeight: 700, color: "#15151F" }}>{vd.vendedor}</div>
      {podeVerValores && (
        <div>
          <div style={{ fontSize: 12, color: GRUPO_CINZA }}>Realizado no mês</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#1D9E75" }}>{fmtBRL(vd.realizado)}</div>
        </div>
      )}
      {temMeta ? (
        <>
          {podeVerValores && (
            <div>
              <div style={{ fontSize: 12, color: GRUPO_CINZA }}>Meta</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#15151F" }}>{fmtBRL(vd.meta as number)}</div>
            </div>
          )}
          <div>
            <div style={{ fontSize: 12, color: GRUPO_CINZA }}>% da meta</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: cor }}>{Math.round(pct * 100)}%</div>
          </div>
        </>
      ) : (
        <div style={{ fontSize: 13, color: GRUPO_CINZA }}>Sem meta cadastrada no Pipedrive para este mês.</div>
      )}
    </div>
  );
}

// ── Conteúdo ──────────────────────────────────────────────────
// Exportado para o Modo TV reusar o painel COMPLETO (todos os 10 blocos).
export function GvContent({ data }: { data: GestaoVistaData }) {
  const { user } = useAuth();
  // Valores em R$ por vendedor (ranking diário, venda/dia) só pros gestores
  // comerciais (Vinícius/Alves). Os demais veem só percentual. Decisão 09/07.
  const podeVerValores = !!(user?.pode_editar_metas || user?.is_admin);
  return (
    <div className="flex flex-col gap-4">
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
          gap: 18,
        }}
      >
        <CardMeta data={data} />
        <CardRankingMensal data={data} />
        <CardRankingDiario data={data} podeVerValores={podeVerValores} />
        <CardVendaDia data={data} podeVerValores={podeVerValores} />
        <CardPipeline num={5} titulo="Pipeline aberto — Hospitalar" stats={data.pipeline_hosp} />
        <CardPipeline num={6} titulo="Pipeline aberto — Farmácia" stats={data.pipeline_farma} />
        <CardEngReversa num={7} titulo="Engenharia reversa — Hospitalar" eng={data.eng_reversa_hosp} />
        <CardEngReversa num={8} titulo="Engenharia reversa — Farmácia" eng={data.eng_reversa_farma} />
        <AtividadesComFiltro data={data} />
      </div>

      {/* 5) Rodapé */}
      <div
        style={{
          background: "#EEF0FF", color: "#1E1882", borderRadius: 14,
          padding: "14px 22px", fontSize: 13, fontWeight: 600,
        }}
      >
        ★ Nosso foco, nosso resultado — disciplina todos os dias, resultados todos os meses.
      </div>
    </div>
  );
}

// ── Card 1: % da meta da equipe (gauge) ───────────────────────
function CardMeta({ data }: { data: GestaoVistaData }) {
  const { user } = useAuth();
  const [editando, setEditando] = useState(false);
  const podeEditar = !!(user?.pode_editar_metas || user?.is_admin);

  const pct = data.pct_meta;
  const clamped = Math.max(0, Math.min(pct, 1));
  const cor = pct >= 0.85 ? "#1D9E75" : pct >= 0.5 ? "#D97706" : "#DC2626";
  const arc = "M18,84 A64,64 0 0 1 146,84";

  const chips: { label: string; valor: number }[] = [
    { label: "Hospitalar", valor: data.canais.FA },
    { label: "Farmácia", valor: data.canais.FR },
  ];
  // SAC entrou no Hospitalar a partir de Julho/2026 — some do canal só de julho
  // em diante; meses passados mantêm SAC pra auditoria.
  if (data.mes < SAC_FIM) chips.push({ label: "SAC", valor: data.canais.PC });
  if (data.canais.MKT != null) chips.push({ label: "Marketplace", valor: data.canais.MKT });

  return (
    <GvCard num={1} title="% da meta da equipe" fonte="ERP + CRM" wide>
      <div style={{ display: "flex", alignItems: "center", gap: 28, flexWrap: "wrap" }}>
        <svg viewBox="0 0 164 96" width={140} style={{ flexShrink: 0 }}>
          <path d={arc} stroke="#EEF0FF" strokeWidth={14} strokeLinecap="round" fill="none" />
          <path
            d={arc}
            stroke={cor}
            strokeWidth={14}
            strokeLinecap="round"
            fill="none"
            strokeDasharray={`${clamped * 201.06} 201.06`}
          />
          <text x={82} y={78} textAnchor="middle" fontSize={30} fontWeight={600} fill="#15151F">
            {`${Math.round(pct * 100)}%`}
          </text>
        </svg>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 13, color: GRUPO_CINZA, display: "flex", alignItems: "center", gap: 8 }}>
            <span>
              Meta <b style={{ color: "#15151F" }}>{fmtBRL(data.meta)}</b>
            </span>
            {podeEditar && (
              <button
                type="button"
                onClick={() => setEditando(true)}
                title="Editar meta"
                aria-label="Editar meta"
                style={{
                  background: "transparent",
                  border: "none",
                  padding: 2,
                  cursor: "pointer",
                  color: "rgba(107,107,122,0.75)",
                  display: "inline-flex",
                  alignItems: "center",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.color = "#15151F"; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = "rgba(107,107,122,0.75)"; }}
              >
                <Pencil size={14} />
              </button>
            )}
          </div>
          <div style={{ fontSize: 13, color: GRUPO_CINZA }}>
            Realizado <b style={{ color: "#15151F" }}>{fmtBRL(data.faturado_mes)}</b>
          </div>
          <div style={{ fontSize: 13, color: GRUPO_CINZA }}>
            Falta: <b style={{ color: cor }}>{fmtBRL(data.falta)}</b>{" "}
            ({data.meta ? Math.round((data.falta / data.meta) * 100) : 0}%)
          </div>
          {/* Caption "Atualizada por ..." pendente do backend retornar meta_updated_at/updated_by:
          {data.meta_updated_at && (
            <Caption>
              Atualizada por {data.meta_updated_by} em {fmtDataHora(data.meta_updated_at)}
            </Caption>
          )}
          */}
        </div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 18 }}>
        {chips.map((c) => (
          <div
            key={c.label}
            style={{
              background: "#F7F7FB", borderRadius: 10, padding: "8px 12px",
              minWidth: 92, flex: "1 1 auto",
            }}
          >
            <div style={{ fontSize: 10.5, color: GRUPO_CINZA }}>{c.label}</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "#15151F", marginTop: 2 }}>
              {brlK(c.valor)}
            </div>
          </div>
        ))}
      </div>

      {editando && (
        <ModalEditarMeta
          data={data}
          onClose={() => setEditando(false)}
        />
      )}
    </GvCard>
  );
}

// ── Modal: editar meta do mês ─────────────────────────────────
function ModalEditarMeta({
  data, onClose,
}: {
  data: GestaoVistaData; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const salvar = useSalvarMeta();
  const [valor, setValor] = useState<string>(String(data.meta ?? 0));
  const [erro, setErro] = useState<string | null>(null);

  const submeter = () => {
    const nova = Number(valor);
    if (!isFinite(nova) || nova < 0) {
      setErro("Informe um valor numérico válido.");
      return;
    }
    setErro(null);
    salvar.mutate(
      { mes: data.mes, view_key: data.view_key, meta: nova },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["gestao_vista"] });
          onClose();
        },
        onError: (err: unknown) => {
          setErro(err instanceof Error ? err.message : "Falha ao salvar a meta.");
        },
      },
    );
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000, padding: 16,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "#fff", borderRadius: 16, padding: 24,
          maxWidth: 420, width: "100%",
          boxShadow: "0 12px 48px rgba(0,0,0,0.18)",
        }}
      >
        <div style={{ fontSize: 17, fontWeight: 600, color: "#15151F", marginBottom: 6 }}>
          Editar meta de {data.mes_label}
        </div>
        <div style={{ fontSize: 12, color: GRUPO_CINZA, marginBottom: 18 }}>
          Visão {data.view} · valor total do mês em reais
        </div>

        <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "#15151F" }}>
          Meta (R$)
          <input
            type="number"
            step={0.01}
            min={0}
            value={valor}
            autoFocus
            onChange={(e) => setValor(e.target.value)}
            style={{
              border: "1px solid #D9D9E3", borderRadius: 10, padding: "10px 12px",
              fontSize: 15, color: "#15151F", outline: "none",
            }}
          />
        </label>

        {erro && (
          <div style={{ marginTop: 10, fontSize: 12, color: "#B91C1C" }}>{erro}</div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
          <button
            type="button"
            onClick={onClose}
            disabled={salvar.isPending}
            style={{
              background: "transparent", border: "1px solid #D9D9E3",
              borderRadius: 10, padding: "8px 16px", fontSize: 13,
              color: "#15151F", cursor: salvar.isPending ? "default" : "pointer",
            }}
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={submeter}
            disabled={salvar.isPending}
            style={{
              background: "#1E1882", border: "none", borderRadius: 10,
              padding: "8px 16px", fontSize: 13, fontWeight: 600, color: "#fff",
              cursor: salvar.isPending ? "default" : "pointer",
              opacity: salvar.isPending ? 0.7 : 1,
            }}
          >
            {salvar.isPending ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Barra horizontal genérica (track + fill).
function Barra({ width, cor }: { width: number; cor: string }) {
  return (
    <div style={{ background: "#F0F0F5", borderRadius: 999, height: 6, overflow: "hidden" }}>
      <div style={{ width: `${width}%`, background: cor, height: "100%", borderRadius: 999 }} />
    </div>
  );
}

// ── Card 2: ranking mensal ────────────────────────────────────
function CardRankingMensal({ data }: { data: GestaoVistaData }) {
  // Prioriza o % do CRM (negócios ganhos) como número principal + barra; o ERP
  // aparece só como % já faturado (sem valor em R$). Ordena pelo CRM.
  const itens = [...data.ranking_mensal].sort((a, b) => (b.pct_crm ?? 0) - (a.pct_crm ?? 0));
  return (
    <GvCard num={2} title="Ranking mensal" fonte="ERP + CRM">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {itens.map((r) => {
          const pctCrm = r.pct_crm ?? 0;
          const cor = pctCrm >= 0.9 ? "#1D9E75" : pctCrm >= 0.5 ? "#BA7517" : "#E24B4A";
          return (
            <div key={r.vendedor}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                <span style={{ color: "#15151F" }}>{r.vendedor}</span>
                <span style={{ color: GRUPO_CINZA, fontWeight: 600 }}>{Math.round(pctCrm * 100)}%</span>
              </div>
              <Barra width={Math.min(pctCrm, 1) * 100} cor={cor} />
              <div style={{ fontSize: 11, color: "#9A9AA8", marginTop: 3 }}>
                {r.pct == null ? "Sem meta cadastrada" : `ERP faturado: ${Math.round(r.pct * 100)}%`}
              </div>
            </div>
          );
        })}
      </div>
      <Nota>% da meta pelos negócios ganhos no CRM (barra) · "ERP faturado" = % já emitido em nota fiscal</Nota>
    </GvCard>
  );
}

// ── Card 3: ranking diário (remanescente = quanto falta vender hoje) ──
function CardRankingDiario({ data, podeVerValores }: { data: GestaoVistaData; podeVerValores: boolean }) {
  return (
    <GvCard num={3} title="Ranking diário" fonte="CRM (Pipe)">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {data.ranking_diario.map((r) => {
          const semMeta = r.meta_diaria == null;
          const pct = r.pct_hoje;
          const cor = semMeta ? "#9A9AA8" : r.bateu_hoje ? "#1D9E75" : pct != null && pct >= 0.5 ? "#BA7517" : "#E24B4A";
          return (
            <div key={r.vendedor}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                <span style={{ color: "#15151F" }}>{r.vendedor}</span>
                <span style={{ color: cor, fontWeight: 600 }}>
                  {semMeta ? "Sem meta cadastrada"
                    : r.bateu_hoje ? "✓ bateu hoje"
                    : podeVerValores ? `${Math.round((pct ?? 0) * 100)}% · falta ${fmtBRL(r.falta_hoje)}`
                    : `${Math.round((pct ?? 0) * 100)}%`}
                </span>
              </div>
              <Barra
                width={semMeta ? 0 : r.bateu_hoje ? 100 : Math.min((pct ?? 0) * 100, 100)}
                cor={cor}
              />
              {podeVerValores && (
                <div style={{ fontSize: 11, color: "#9A9AA8", marginTop: 3 }}>
                  Vendido hoje (CRM) {fmtBRL(r.vendido_hoje)}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <Nota>
        % da meta diária VENDIDA HOJE no CRM/Pipe (mensal ÷ {data.du_total} dias úteis) ·
        melhor atingimento primeiro
      </Nota>
    </GvCard>
  );
}

// ── Card 4: venda necessária por dia ──────────────────────────
function CardVendaDia({ data, podeVerValores }: { data: GestaoVistaData; podeVerValores: boolean }) {
  const vmax = Math.max(1, ...data.venda_necessaria_dia.map((v) => v.venda_dia));
  return (
    <GvCard num={4} title="Venda necessária por dia" fonte="ERP + CRM">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {data.venda_necessaria_dia.map((v) => (
          <div key={v.vendedor}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
              <span style={{ color: "#15151F" }}>{v.vendedor}</span>
              <span style={{ color: v.batida ? "#1D9E75" : GRUPO_CINZA, fontWeight: 600 }}>
                {v.batida ? "✓ meta batida" : podeVerValores ? `${fmtBRL(v.venda_dia)}/dia` : "em aberto"}
              </span>
            </div>
            <Barra
              width={v.batida ? 100 : Math.max((v.venda_dia / vmax) * 100, 4)}
              cor={v.batida ? "#1D9E75" : "#6D5FD6"}
            />
          </div>
        ))}
      </div>
      <Nota>
        Quanto cada um precisa vender por dia útil restante pra bater a meta
        {podeVerValores ? " · (meta − realizado) ÷ dias úteis restantes" : " · valor visível só para gestores"}
      </Nota>
    </GvCard>
  );
}

// ── Cards 5/6: pipeline aberto ────────────────────────────────
function CardPipeline({ num, titulo, stats }: { num: number; titulo: string; stats: GvPipelineStats }) {
  const vazio = stats.stages.length === 0 || stats.stages.every((s) => s.valor === 0);
  const vmax = Math.max(1, ...stats.stages.map((s) => s.valor));

  return (
    <GvCard num={num} title={titulo} fonte="CRM">
      {vazio ? (
        <InfoBox>Pipedrive sem dados neste pipeline</InfoBox>
      ) : (
        <>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#15151F", marginBottom: 14 }}>
            {brlK(stats.pipe_open)} em aberto
            {stats.win_rate != null && (
              <span style={{ fontSize: 12, fontWeight: 500, color: GRUPO_CINZA, marginLeft: 10 }}>
                win rate {Math.round(stats.win_rate * 100)}%
              </span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {stats.stages.map((s) => (
              <div key={s.nome}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                  <span style={{ color: "#15151F" }}>{s.nome}</span>
                  <span style={{ color: GRUPO_CINZA, fontWeight: 600 }}>{brlK(s.valor)}</span>
                </div>
                <Barra width={Math.max((s.valor / vmax) * 100, 3)} cor="#378ADD" />
              </div>
            ))}
          </div>
        </>
      )}
      <Nota>Pipedrive ao vivo · top estágios por valor</Nota>
    </GvCard>
  );
}

// ── Cards 7/8: engenharia reversa ─────────────────────────────
function CardEngReversa({ num, titulo, eng }: { num: number; titulo: string; eng: GvEngReversa }) {
  return (
    <GvCard num={num} title={titulo} fonte="CRM" wide>
      {eng.vazio ? (
        <InfoBox>Sem vendedores com meta neste grupo</InfoBox>
      ) : (
        <>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#15151F" }}>
            {fmtBRL(eng.meta_tot)} restante do grupo
            {eng.aprox && (
              <span
                style={{
                  fontSize: 11, fontWeight: 600, color: "#854F0B", background: "#FAEEDA",
                  borderRadius: 999, padding: "2px 8px", marginLeft: 10, verticalAlign: "middle",
                }}
              >
                taxas aprox.
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: GRUPO_CINZA, marginTop: 2, marginBottom: 14 }}>
            ticket médio {fmtBRL(eng.ticket)} · funil necessário pra bater o restante da meta no mês (já descontado o que foi vendido)
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, alignItems: "center" }}>
            {(eng.etapas ?? []).map((e, i) => (
              <div key={i} style={{ width: "100%", display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div
                  style={{
                    height: 22, background: e.cor, width: `${e.largura}%`, minWidth: 80,
                    borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                    padding: "0 10px", color: "#fff", fontSize: 12.5, fontWeight: 600,
                  }}
                >
                  <span>{e.label}</span>
                  <span style={{ opacity: 0.9 }}>{fmtNum(e.valor)}</span>
                </div>
                <div style={{ fontSize: 11, color: GRUPO_CINZA, marginTop: 3, textAlign: "center" }}>{e.caption}</div>
              </div>
            ))}
          </div>
        </>
      )}
      <Nota>Meta ÷ ticket médio ÷ taxas de conversão do funil</Nota>
    </GvCard>
  );
}

// ── Cards 9/10: atividades ────────────────────────────────────
// Filtro de período pras atividades (pedido do Alves 07/07 pt.3): "no melhor
// dos mundos, um filtro de data pra escolhermos" — em vez de ficar preso ao
// mês inteiro, dá pra ver Hoje / Últimos 7 dias / Mês inteiro. "Mês inteiro"
// reusa o payload principal (sem fetch extra); os outros dois buscam à parte.
function AtividadesComFiltro({ data }: { data: GestaoVistaData }) {
  // Padrão "hoje" (pedido 16/07) — antes abria em "mês inteiro" e escondia o
  // atraso do dia atrás do acumulado do mês.
  const [periodo, setPeriodo] = useState<"hoje" | "semana" | "mes">("hoje");

  const hojeISO = new Date().toISOString().slice(0, 10);
  const semanaISO = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10);
  const de = periodo === "hoje" ? hojeISO : periodo === "semana" ? semanaISO : undefined;
  const ate = periodo === "mes" ? undefined : hojeISO;

  const custom = useAtividadesPeriodo(de, ate);
  const usandoMes = periodo === "mes";
  const tipo = usandoMes ? data.atividades_tipo : (custom.data?.atividades_tipo ?? null);
  const vendedor = usandoMes ? data.atividades_vendedor : (custom.data?.atividades_vendedor ?? null);
  const sufixoNota = periodo === "hoje" ? "hoje" : periodo === "semana" ? "últimos 7 dias" : "mês inteiro";

  return (
    <>
      <div style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: GRUPO_CINZA, fontWeight: 600 }}>Atividades no período:</span>
        {([
          { key: "hoje", label: "Hoje" },
          { key: "semana", label: "Últimos 7 dias" },
          { key: "mes", label: "Mês inteiro" },
        ] as const).map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => setPeriodo(p.key)}
            style={{
              fontSize: 12, fontWeight: 600, padding: "4px 12px", borderRadius: 999,
              border: `1px solid ${periodo === p.key ? "#1E1882" : "#E6E7F2"}`,
              background: periodo === p.key ? "#1E1882" : "#fff",
              color: periodo === p.key ? "#fff" : "#374151", cursor: "pointer",
            }}
          >
            {p.label}
          </button>
        ))}
        {!usandoMes && custom.isLoading && <span style={{ fontSize: 12, color: GRUPO_CINZA }}>carregando…</span>}
      </div>
      <CardAtividades
        num={9}
        titulo="Atividades por tipo"
        itens={tipo}
        chaveLabel="tipo"
        notaVazia="crm_raw.activities indisponível"
        nota={`Ranqueado por feitas · toda a equipe · ${sufixoNota}`}
      />
      <CardAtividades
        num={10}
        titulo="Atividades por vendedor"
        itens={vendedor}
        chaveLabel="vendedor"
        notaVazia="crm_raw.activities indisponível"
        nota={`Feitas no período (${sufixoNota}) · atrasadas sem data no Pipedrive`}
      />
    </>
  );
}

function CardAtividades({
  num, titulo, itens, chaveLabel, notaVazia, nota,
}: {
  num: number; titulo: string;
  itens: { tipo?: string; vendedor?: string; concl: number; atras: number }[] | null;
  chaveLabel: "tipo" | "vendedor"; notaVazia: string; nota: string;
}) {
  if (itens === null) {
    return (
      <GvCard num={num} title={titulo} fonte="CRM">
        <InfoBox>{notaVazia}</InfoBox>
        <Nota>{nota}</Nota>
      </GvCard>
    );
  }

  const totConcl = itens.reduce((acc, it) => acc + it.concl, 0);
  const totAtras = itens.reduce((acc, it) => acc + it.atras, 0);
  const vmax = Math.max(1, ...itens.map((it) => it.concl));

  return (
    <GvCard num={num} title={titulo} fonte="CRM">
      <div style={{ fontSize: 13, color: GRUPO_CINZA, marginBottom: 14 }}>
        <b style={{ color: "#15151F" }}>{totConcl}</b> feitas ·{" "}
        <b style={{ color: "#15151F" }}>{totAtras}</b> atrasadas no mês
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {itens.map((it, i) => {
          const label = chaveLabel === "tipo" ? it.tipo : it.vendedor;
          const cor = ATIV_CORES[i % ATIV_CORES.length];
          return (
            <div key={label ?? i}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4, gap: 8 }}>
                <span style={{ color: "#15151F" }}>{label}</span>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ color: GRUPO_CINZA, fontWeight: 600 }}>{it.concl}</span>
                  {it.atras > 0 && (
                    <span
                      style={{
                        fontSize: 10.5, fontWeight: 600, color: "#B91C1C", background: "#FEE2E2",
                        borderRadius: 999, padding: "1px 7px",
                      }}
                    >
                      {it.atras} atras
                    </span>
                  )}
                </span>
              </div>
              <Barra width={Math.max((it.concl / vmax) * 100, 3)} cor={cor} />
            </div>
          );
        })}
      </div>
      <Nota>{nota}</Nota>
    </GvCard>
  );
}
