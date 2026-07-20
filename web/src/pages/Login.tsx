import { useState, type FormEvent } from "react";
import { Mail, Lock, Eye, EyeOff, ArrowRight, Loader2 } from "lucide-react";
import { NEVONI } from "../theme";

// Base da API (mesmo padrão de lib/api.ts). Vazio em dev por conta do proxy do Vite.
const API_BASE = (import.meta.env as Record<string, string | undefined>).VITE_API_BASE_URL ?? "";

interface LoginUser {
  id: number;
  email: string;
  nome: string;
  is_admin: boolean;
  pode_editar_metas: boolean;
  pode_usar_oraculo: boolean;
  precisa_trocar_senha: boolean;
}
interface LoginResponse { user: LoginUser; }

async function fazerLogin(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let detail = "E-mail ou senha incorretos.";
    try { const b = await res.json(); if (typeof b?.detail === "string" && b.detail.trim()) detail = b.detail; } catch { /* padrão */ }
    throw new Error(detail);
  }
  return res.json() as Promise<LoginResponse>;
}

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await fazerLogin(email.trim(), password);
      // Vai direto pro dashboard (não temos mais tela de trocar senha).
      window.location.href = "/";
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao entrar.");
      setEnviando(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex flex-col md:flex-row bg-white">
      {/* ── Lado esquerdo (marca) ──────────────────────────────── */}
      <section
        className="relative w-full md:w-[65%] flex flex-col justify-between overflow-hidden text-white px-8 py-10 md:px-16 md:py-14 min-h-[320px] md:min-h-screen"
        style={{
          background: "radial-gradient(140% 120% at 0% 0%, #0A0838 0%, #15104F 32%, #1E1882 62%, #251EA8 100%)",
        }}
      >
        {/* Linhas topográficas decorativas (brancas ~10%, 9 linhas distribuídas por toda a altura) */}
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox="0 0 1000 1000"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden
        >
          {Array.from({ length: 9 }).map((_, i) => (
            <path
              key={i}
              d={`M -200 ${120 + i * 100} C 200 ${40 + i * 100}, 600 ${200 + i * 100}, 1200 ${80 + i * 100}`}
              fill="none"
              stroke="rgba(255,255,255,0.10)"
              strokeWidth={1}
            />
          ))}
        </svg>

        {/* Topo: logo Nevoni */}
        <div className="relative z-10">
          <img
            src="/nevoni_logo.png"
            alt="Nevoni"
            style={{ width: 96, height: 96, filter: "drop-shadow(0 8px 22px rgba(0,0,0,0.35))" }}
          />
        </div>

        {/* Hero */}
        <div className="relative z-10 max-w-xl mt-6 md:mt-0">
          <h1
            className="m-0 leading-[1.05]"
            style={{
              fontFamily: 'var(--font-sans, "Inter", system-ui, sans-serif)',
              fontWeight: 700,
              fontSize: "clamp(38px, 5.4vw, 58px)",
              letterSpacing: "-0.02em",
            }}
          >
            Nevoni 360
          </h1>
          <p
            className="mt-5 text-white/80 leading-relaxed"
            style={{ fontSize: "15.5px", maxWidth: "46ch" }}
          >
            Agentes, dados e entregas conectados para transformar a rotina em eficiência. Com governança e inteligência aplicadas.
          </p>
        </div>

        {/* Rodapé Vanguardia — monograma V grande + assinatura */}
        <div className="relative z-10 mt-8 md:mt-0 flex items-center gap-4">
          <svg width="56" height="56" viewBox="0 0 40 40" aria-hidden>
            <path
              d="M4 6 L20 34 L36 6 L30 6 L20 22 L10 6 Z"
              fill="rgba(255,255,255,0.18)"
            />
          </svg>
          <span
            className="text-[11px] uppercase"
            style={{ letterSpacing: "0.32em", color: "rgba(255,255,255,0.55)" }}
          >
            Created by Vanguardia
          </span>
        </div>
      </section>

      {/* ── Lado direito (formulário) ──────────────────────────── */}
      <section className="w-full md:w-[35%] flex items-center justify-center px-6 py-10 md:px-14 bg-white">
        <div className="w-full max-w-sm">
          <header className="mb-8">
            <h2 className="text-[24px] leading-tight font-semibold" style={{ color: "#111827" }}>
              Acesse sua conta
            </h2>
            <p className="text-sm mt-1" style={{ color: NEVONI.primary }}>
              Entre para continuar.
            </p>
          </header>

          {erro && (
            <div
              role="alert"
              className="mb-4 rounded-lg border px-3 py-2 text-sm"
              style={{ background: "#FEF2F2", borderColor: "#FCA5A5", color: "#B91C1C" }}
            >
              {erro}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <label className="block">
              <span className="block text-[13px] font-medium mb-1.5" style={{ color: "#374151" }}>
                E-mail
              </span>
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "#9CA3AF" }} />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  placeholder="seu@email.com"
                  className="w-full rounded-xl pl-9 pr-3 py-2.5 text-sm outline-none border transition-shadow"
                  style={{ background: "#F4F5FB", borderColor: "#E6E7F2", color: "#15151F" }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = NEVONI.primary;
                    e.currentTarget.style.boxShadow = "0 0 0 3px rgba(30,24,130,0.12)";
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = "#E6E7F2";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                />
              </div>
            </label>

            <label className="block">
              <span className="block text-[13px] font-medium mb-1.5" style={{ color: "#374151" }}>
                Senha
              </span>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "#9CA3AF" }} />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                  placeholder="Sua senha"
                  className="w-full rounded-xl pl-9 pr-10 py-2.5 text-sm outline-none border transition-shadow"
                  style={{ background: "#F4F5FB", borderColor: "#E6E7F2", color: "#15151F" }}
                  onFocus={(e) => {
                    e.currentTarget.style.borderColor = NEVONI.primary;
                    e.currentTarget.style.boxShadow = "0 0 0 3px rgba(30,24,130,0.12)";
                  }}
                  onBlur={(e) => {
                    e.currentTarget.style.borderColor = "#E6E7F2";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md"
                  style={{ color: "#6B7280" }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <div className="flex justify-end mt-1.5">
                <button
                  type="button"
                  onClick={() => alert("Para redefinir sua senha, fale com o administrador do sistema.")}
                  className="text-[13px] font-medium"
                  style={{ color: NEVONI.primary }}
                >
                  Esqueci minha senha
                </button>
              </div>
            </label>

            <button
              type="submit"
              disabled={enviando || !email || !password}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 text-[15px] font-semibold text-white mt-3 transition-[filter] disabled:opacity-60 disabled:cursor-not-allowed"
              style={{
                background: `linear-gradient(135deg, ${NEVONI.primary} 0%, #3A33B8 100%)`,
                boxShadow: "0 8px 20px rgba(30,24,130,0.28)",
              }}
              onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.filter = "brightness(1.08)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.filter = "none"; }}
            >
              {enviando ? (<><Loader2 size={16} className="animate-spin" /> Entrando…</>) : (<>Entrar <ArrowRight size={16} /></>)}
            </button>
          </form>

          <p className="mt-8 text-[11.5px] text-center" style={{ color: "#9CA3AF" }}>
            Problemas para entrar? Fale com o administrador do sistema.
          </p>
        </div>
      </section>
    </div>
  );
}
