import { useEffect, useState } from "react";
import { X } from "lucide-react";

// Relógio grande que atualiza a cada segundo (TV fica ligada o dia todo).
function useRelogio(): string {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export const TV_MUTED = "rgba(255,255,255,0.58)";

// Shell dark reutilizável do Modo TV: overlay tela cheia, barra superior com
// relógio ao vivo + Sair, Esc pra fechar, trava de scroll e fullscreen.
export function TvShell({
  titulo, chip, carga, onClose, children,
}: {
  titulo: string; chip?: string; carga?: string; onClose: () => void; children: React.ReactNode;
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
    <div style={{
      position: "fixed", inset: 0, zIndex: 9999, color: "#fff",
      background: "radial-gradient(130% 130% at 0% 0%, #0A0838 0%, #15104F 40%, #1E1882 100%)",
      display: "flex", flexDirection: "column", overflow: "hidden",
      fontFamily: 'var(--font-sans, "Inter", system-ui, sans-serif)',
    }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, padding: "clamp(12px,1.2vw,22px) clamp(20px,2vw,40px)", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
          <span style={{ fontSize: "clamp(11px,0.9vw,14px)", letterSpacing: ".26em", color: "#C9A45A", fontWeight: 600, textTransform: "uppercase" }}>Nevoni 360</span>
          <span style={{ fontSize: "clamp(20px,2vw,36px)", fontWeight: 700 }}>{titulo}</span>
          {chip && <span style={{ fontSize: "clamp(12px,1vw,17px)", fontWeight: 600, background: "rgba(255,255,255,0.14)", padding: "3px 14px", borderRadius: 999 }}>{chip}</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "clamp(20px,2vw,34px)", fontWeight: 700, lineHeight: 1, fontVariantNumeric: "tabular-nums" }}>{relogio}</div>
            {carga && <div style={{ fontSize: "clamp(9px,0.75vw,12px)", color: TV_MUTED, marginTop: 3 }}>Atualiza sozinho · carga {carga}</div>}
          </div>
          <button type="button" onClick={onClose} aria-label="Sair do Modo TV" title="Sair (Esc)"
            style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(255,255,255,0.10)", border: "1px solid rgba(255,255,255,0.20)", color: "#fff", borderRadius: 10, padding: "8px 14px", cursor: "pointer", fontSize: "clamp(11px,0.9vw,14px)", fontWeight: 600 }}>
            <X size={16} /> Sair
          </button>
        </div>
      </header>
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", padding: "0 clamp(20px,2vw,40px) clamp(16px,1.5vw,30px)" }}>
        {children}
      </div>
    </div>
  );
}

// Card grande de KPI pro Modo TV (número protagonista + rótulo + delta opcional).
export function TvKpi({ label, value, delta, deltaBom, destaque }: {
  label: string; value: string; delta?: string; deltaBom?: boolean; destaque?: "verde" | "vermelho";
}) {
  const cor = destaque === "verde" ? "#34D399" : destaque === "vermelho" ? "#F87171" : "#fff";
  return (
    <div style={{
      background: "rgba(255,255,255,0.055)", border: "1px solid rgba(255,255,255,0.10)",
      borderRadius: 18, padding: "clamp(16px,1.6vw,30px)", minHeight: 0, overflow: "hidden",
      display: "flex", flexDirection: "column", justifyContent: "center", gap: 8,
    }}>
      <div style={{ fontSize: "clamp(11px,1vw,16px)", color: TV_MUTED, textTransform: "uppercase", letterSpacing: ".07em" }}>{label}</div>
      <div style={{ fontSize: "clamp(24px,2.6vw,48px)", fontWeight: 700, lineHeight: 1.05, color: cor, fontVariantNumeric: "tabular-nums" }}>{value}</div>
      {delta && (
        <div style={{ fontSize: "clamp(12px,1.1vw,18px)", fontWeight: 600, color: deltaBom ? "#34D399" : "#F87171" }}>{delta}</div>
      )}
    </div>
  );
}
