import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  ShoppingBag,
  PackageSearch,
  Wallet,
  Tag,
  Factory,
  Headphones,
  Microscope,
  Scale,
  Sparkles,
  Users,
  LogOut,
  KeyRound,
  User,
  Menu,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { isPageHidden } from "../lib/access";
import { useAuth } from "../lib/auth";
import { useLogout } from "../lib/api";

const SIDEBAR_GRADIENT = "linear-gradient(180deg, #0D0B50 0%, #1E1882 60%, #2C28A8 100%)";

// ── Sidebar ───────────────────────────────────────────────────
const SECTORS: { Icon: LucideIcon; name: string; to: string; adminOnly?: boolean }[] = [
  { Icon: Activity, name: "Visão Geral", to: "/visao-geral" },
  { Icon: ShoppingBag, name: "Vendas", to: "/comercial" },
  { Icon: PackageSearch, name: "Compras", to: "/compras" },
  { Icon: Wallet, name: "Financeiro", to: "/financeiro" },
  { Icon: Tag, name: "PRICE", to: "/price", adminOnly: true },
  { Icon: Factory, name: "Operacional e Produção", to: "/operacional" },
  { Icon: Headphones, name: "SAC e AT", to: "/sac" },
  { Icon: Microscope, name: "Engenharia e P&D", to: "/engenharia" },
  { Icon: Scale, name: "Jurídico", to: "/juridico" },
  { Icon: Sparkles, name: "Oráculo", to: "/oraculo" },
  { Icon: Users, name: "Usuários", to: "/admin/usuarios", adminOnly: true },
];

export function Sidebar() {
  const { user } = useAuth();
  const logoutMut = useLogout();
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <>
      {/* Barra superior só no celular: logo + hambúrguer. Fica no fluxo normal
          (empurra o conteúdo pra baixo), a aside vira drawer off-canvas. */}
      <div
        className="md:hidden flex items-center justify-between px-4 py-3 text-white shrink-0"
        style={{ background: SIDEBAR_GRADIENT }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-9 h-9 rounded-full inline-flex items-center justify-center shrink-0"
            style={{ border: "1px solid var(--color-gold)", background: "transparent" }}
          >
            <span style={{ fontFamily: "var(--font-serif)", fontWeight: 500, fontSize: 18, lineHeight: 1 }}>N</span>
          </div>
          <span className="text-[14px] font-bold">
            Nevoni <span style={{ color: "var(--color-gold)" }}>360</span>
          </span>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Abrir menu"
          className="p-1.5 text-white/85 hover:text-white"
        >
          <Menu size={22} />
        </button>
      </div>

      {/* Fundo escuro atrás do drawer aberto (só celular) */}
      {open && (
        <div
          className="md:hidden fixed inset-0 z-40 bg-black/50"
          onClick={close}
          aria-hidden
        />
      )}

      <aside
        className={`
          fixed md:static inset-y-0 left-0 z-50 w-64 shrink-0 text-white flex flex-col
          overflow-y-auto transition-transform duration-200 ease-in-out
          ${open ? "translate-x-0" : "-translate-x-full"} md:translate-x-0
        `}
        style={{ background: SIDEBAR_GRADIENT }}
      >
        <button
          type="button"
          onClick={close}
          aria-label="Fechar menu"
          className="md:hidden self-end mr-3 mt-3 p-1 text-white/70 hover:text-white"
        >
          <X size={20} />
        </button>
        <div className="text-center pt-2 md:pt-5 pb-3">
          <div
            className="w-14 h-14 rounded-full inline-flex items-center justify-center mb-2"
            style={{ border: "1px solid var(--color-gold)", background: "transparent" }}
          >
            <span
              className="text-white tracking-tight"
              style={{ fontFamily: "var(--font-serif)", fontWeight: 500, fontSize: 28, lineHeight: 1 }}
            >
              N
            </span>
          </div>
          <div className="text-white text-[15px] font-bold">Nevoni</div>
          <div className="text-white/40 text-[10px] uppercase tracking-widest">
            <span style={{ color: "var(--color-gold)" }}>360</span> · PLATAFORMA
          </div>
        </div>
        <hr className="border-white/15 mx-4 mb-3" />
        <nav className="flex flex-col gap-1 px-3">
          {SECTORS.map((s) => {
            if (s.adminOnly && !user?.is_admin) return null;
            if (isPageHidden(user, s.to)) return null;
            return (
              <NavLink
                key={s.to}
                to={s.to}
                onClick={close}
                className={({ isActive }) =>
                  `group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors
                  ${isActive ? "bg-white/12 text-white font-semibold" : "text-white/55 hover:text-white/85"}`
                }
              >
                <s.Icon size={18} strokeWidth={1.5} className="text-white/80 group-hover:text-white" />
                <span>{s.name}</span>
              </NavLink>
            );
          })}
        </nav>
        {user && (
          <div className="rounded-lg border-t border-white/10 pt-3 mt-3 px-3 pb-3">
            <div className="flex items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-full inline-flex items-center justify-center shrink-0"
                style={{ background: "#0A1440" }}
              >
                <User size={16} strokeWidth={1.5} className="text-white/80" />
              </div>
              <div className="text-[13px] font-medium text-white truncate">{user.nome}</div>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <NavLink
                to="/trocar-senha"
                onClick={close}
                className="inline-flex items-center gap-1.5 text-[12px] text-white/55 hover:text-white/85 transition-colors"
              >
                <KeyRound size={13} strokeWidth={1.5} />
                <span>Trocar senha</span>
              </NavLink>
              <button
                type="button"
                onClick={() => logoutMut.mutate()}
                disabled={logoutMut.isPending}
                className="inline-flex items-center gap-1.5 text-[12px] text-white/55 hover:text-white/85 transition-colors disabled:opacity-50"
              >
                <LogOut size={13} strokeWidth={1.5} />
                <span>Sair</span>
              </button>
            </div>
          </div>
        )}
        <div className={`${user ? "" : "mt-auto"} px-4 pb-5 pt-3 text-center`}>
          <div
            className="uppercase text-white/30"
            style={{ fontSize: 9, letterSpacing: "0.35em" }}
          >
            CREATED BY
          </div>
          <div
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 500,
              fontSize: 15,
              color: "var(--color-gold)",
              letterSpacing: "0.1em",
            }}
          >
            VANGUARDIA
          </div>
        </div>
      </aside>
    </>
  );
}

// ── Page header ───────────────────────────────────────────────
export function PageHeader({
  title, subtitle, sources,
}: {
  title: string; subtitle?: string; sources?: { name: string; active: boolean }[];
}) {
  return (
    <div
      className="rounded-2xl text-white px-8 py-7 mb-5"
      style={{ background: "linear-gradient(135deg, #0A1440 0%, #1E1882 100%)" }}
    >
      <h1
        style={{ fontFamily: "var(--font-serif)" }}
        className="text-[32px] font-medium tracking-tight leading-tight m-0 mb-2"
      >
        {title}
      </h1>
      <div style={{ width: 40, height: 2, background: "var(--color-gold)" }} className="mb-3" />
      {subtitle && (
        <p className="text-[13.5px] text-white/70 leading-relaxed m-0 max-w-2xl">{subtitle}</p>
      )}
      {sources && sources.some((s) => s.active) && (
        <div className="flex flex-wrap gap-2 border-t border-white/10 pt-3 mt-3">
          {sources
            .filter((s) => s.active)
            .map((s) => (
              <span
                key={s.name}
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs bg-white/12 text-white/90"
              >
                <span
                  className="inline-block rounded-full"
                  style={{ width: 6, height: 6, background: "var(--color-gold)" }}
                />
                {s.name}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

// ── Tabs ──────────────────────────────────────────────────────
export function Tabs({
  tabs, active, onChange,
}: {
  tabs: { id: string; label: string }[]; active: string; onChange: (id: string) => void;
}) {
  return (
    <div className="flex gap-2 border-b border-gray-200 mb-5 overflow-x-auto">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`px-5 py-3 text-sm font-semibold whitespace-nowrap border-b-[3px] -mb-px transition-colors
            ${active === t.id
              ? "text-[#1E1882] border-[#1E1882]"
              : "text-gray-500 border-transparent hover:text-gray-700"}`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Row({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`grid gap-4 ${className}`}>{children}</div>;
}
