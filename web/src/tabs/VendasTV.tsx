import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import CalendarioVendas from "../components/CalendarioVendas";
import FaturamentoMensal from "../components/FaturamentoMensal";
import { fmtBRL } from "../lib/format";
import type { VendasData } from "../lib/api";

const DESIGN_WIDTH = 1560;
const MAX_SCALE = 1.9;

function useRelogio(): string {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Escala o conteúdo pra caber inteiro na área — sem rolagem.
function FitToScreen({ children }: { children: React.ReactNode }) {
  const areaRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  useLayoutEffect(() => {
    const recompute = () => {
      const area = areaRef.current, content = contentRef.current;
      if (!area || !content) return;
      const s = Math.min(area.clientWidth / (content.scrollWidth || DESIGN_WIDTH), area.clientHeight / (content.scrollHeight || 1), MAX_SCALE);
      if (s > 0 && Number.isFinite(s)) setScale(s);
    };
    recompute();
    const ro = new ResizeObserver(recompute);
    if (areaRef.current) ro.observe(areaRef.current);
    if (contentRef.current) ro.observe(contentRef.current);
    window.addEventListener("resize", recompute);
    return () => { ro.disconnect(); window.removeEventListener("resize", recompute); };
  }, []);
  return (
    <div ref={areaRef} style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
      <div ref={contentRef} style={{ width: DESIGN_WIDTH, flexShrink: 0, transform: `scale(${scale || 0.01})`, transformOrigin: "top center", opacity: scale ? 1 : 0, transition: "opacity .2s ease" }}>
        {children}
      </div>
    </div>
  );
}

// Modo TV da aba Vendas — o que o Vinícius pediu (07/07): calendário de vendas
// diárias, faturamento dos últimos 3 anos e faturamento por canal (sem gráficos).
export default function VendasTV({ data, mes, onClose }: { data: VendasData; mes: string; onClose: () => void }) {
  const relogio = useRelogio();
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

  const canais = [...data.canais].sort((a, b) => b.faturamento - a.faturamento);

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: "#EEEEF4", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: 'var(--font-sans, "Inter", system-ui, sans-serif)' }}>
      {/* barra superior */}
      <header style={{ background: "linear-gradient(90deg, #15104F 0%, #1E1882 60%, #2C28A8 100%)", color: "#fff", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, padding: "12px 28px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
          <span style={{ fontSize: 20, fontWeight: 700 }}>Vendas</span>
          <span style={{ fontSize: 15, color: "rgba(255,255,255,0.75)" }}>{data.label_ref}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{relogio}</div>
          <button type="button" onClick={onClose} aria-label="Sair do Modo TV" title="Sair (Esc)"
            style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(255,255,255,0.12)", border: "1px solid rgba(255,255,255,0.22)", color: "#fff", borderRadius: 10, padding: "8px 14px", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
            <X size={16} /> Sair
          </button>
        </div>
      </header>

      <div style={{ flex: 1, minHeight: 0, padding: "18px 24px" }}>
        <FitToScreen>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {/* Linha de cima: calendário (esquerda) + faturamento por canal (direita),
                lado a lado — layout pedido pelo Vinícius (reunião 09/07). */}
            <div style={{ display: "flex", gap: 18, alignItems: "stretch" }}>
              <div style={{ flex: "1 1 0", minWidth: 0, display: "flex", flexDirection: "column", gap: 14 }}>
                <CalendarioVendas mes={mes} />
              </div>

              {/* Faturamento por canal — coluna à direita, lista vertical */}
              <div style={{ flex: "0 0 380px", background: "#fff", border: "1px solid #ECECF3", borderRadius: 14, padding: "18px 22px", display: "flex", flexDirection: "column" }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: "#15151F", marginBottom: 14 }}>Faturamento por canal — {data.label_ref}</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {canais.map((c) => (
                    <div key={c.canal} style={{ background: "#F7F7FB", borderRadius: 10, padding: "12px 14px" }}>
                      <div style={{ fontSize: 13, color: "#6B6B7A", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.canal}</div>
                      <div style={{ fontSize: 24, fontWeight: 700, color: "#15151F", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>{fmtBRL(c.faturamento)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Linha de baixo: faturamento mensal — 3 anos (largura total) */}
            <FaturamentoMensal />
          </div>
        </FitToScreen>
      </div>
    </div>
  );
}
