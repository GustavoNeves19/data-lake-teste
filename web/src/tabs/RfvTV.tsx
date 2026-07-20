import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { RfvContent } from "./RfvTab";
import type { RfvData } from "../lib/api";

const DESIGN_WIDTH = 1400;
const MAX_SCALE = 1.8;

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

// Select compacto p/ o header escuro do Modo TV (nativo, estilizado).
function TvSelect({ value, onChange, options }: {
  value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        background: "rgba(255,255,255,0.14)", color: "#fff", border: "1px solid rgba(255,255,255,0.28)",
        borderRadius: 8, padding: "5px 10px", fontSize: 13, fontWeight: 600, cursor: "pointer",
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value} style={{ color: "#15151F" }}>{o.label}</option>
      ))}
    </select>
  );
}

// Modo TV da Matriz RFV — reusa o MESMO conteúdo da tela normal (RfvContent),
// só amplia pra tela cheia. Pedido do Vinícius: "tem que ficar igual enxergarmos
// sem modo TV" — nada de simplificar, é a mesma matriz + KPIs + detalhes. Os
// filtros (família/vendedor/período) ficam no header pra alternar sem sair da TV
// (reunião 09/07 — antes só dava pra ver o "Geral").
export default function RfvTV({
  data, familia, carteira, periodo, familias, carteiras, periodos,
  onFamilia, onCarteira, onPeriodo, onClose,
}: {
  data: RfvData; familia: string; carteira: string; periodo: string;
  familias: string[]; carteiras: { value: string; label: string }[]; periodos: { value: string; label: string }[];
  onFamilia: (v: string) => void; onCarteira: (v: string) => void; onPeriodo: (v: string) => void;
  onClose: () => void;
}) {
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

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: "#EEEEF4", display: "flex", flexDirection: "column", overflow: "hidden", fontFamily: 'var(--font-sans, "Inter", system-ui, sans-serif)' }}>
      <header style={{ background: "linear-gradient(90deg, #15104F 0%, #1E1882 60%, #2C28A8 100%)", color: "#fff", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, padding: "12px 28px", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 20, fontWeight: 700 }}>Matriz RFV</span>
          <TvSelect value={familia} onChange={onFamilia}
            options={familias.map((f) => ({ value: f, label: f }))} />
          <TvSelect value={carteira} onChange={onCarteira} options={carteiras} />
          {periodos.length > 0 && (
            <TvSelect value={periodo} onChange={onPeriodo} options={periodos} />
          )}
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
          <RfvContent data={data} familia={familia} carteira={carteira} periodo={periodo} />
        </FitToScreen>
      </div>
    </div>
  );
}
