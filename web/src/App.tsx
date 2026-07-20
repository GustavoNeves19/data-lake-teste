import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Sidebar } from "./components/layout";
import { Spinner } from "./components/ui";
import ComingSoon from "./components/ComingSoon";
import { AuthProvider, Guard, AdminGuard, PageGuard } from "./lib/auth";

// Páginas de setor carregadas sob demanda (code-splitting).
const Comercial = lazy(() => import("./pages/Comercial"));
const Compras = lazy(() => import("./pages/Compras"));
const VisaoGeral = lazy(() => import("./pages/VisaoGeral"));
const Financeiro = lazy(() => import("./pages/Financeiro"));
const Price = lazy(() => import("./pages/Price"));
const Sac = lazy(() => import("./pages/Sac"));
const Operacional = lazy(() => import("./pages/Operacional"));
const Engenharia = lazy(() => import("./pages/Engenharia"));
const Oraculo = lazy(() => import("./pages/Oraculo"));
const Login = lazy(() => import("./pages/Login"));
const TrocarSenha = lazy(() => import("./pages/TrocarSenha"));
const Usuarios = lazy(() => import("./pages/Usuarios"));

// Wrapper que só renderiza a Sidebar nas rotas do dashboard. As telas de auth
// (login e primeiro acesso) ocupam tela cheia.
const AUTH_ROUTES = new Set(["/login"]);

function Shell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  if (AUTH_ROUTES.has(pathname)) {
    return <main className="min-h-screen w-full">{children}</main>;
  }
  return (
    <div className="flex flex-col md:flex-row min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-x-hidden">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Shell>
          <Suspense fallback={<div className="p-16"><Spinner label="Carregando..." /></div>}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/trocar-senha" element={<Guard><TrocarSenha /></Guard>} />
              <Route path="/" element={<Navigate to="/comercial" replace />} />
              <Route path="/comercial" element={<PageGuard page="/comercial"><Comercial /></PageGuard>} />
              <Route path="/compras" element={<PageGuard page="/compras"><Compras /></PageGuard>} />
              <Route path="/visao-geral" element={<PageGuard page="/visao-geral"><VisaoGeral /></PageGuard>} />
              <Route path="/financeiro" element={<PageGuard page="/financeiro"><Financeiro /></PageGuard>} />
              <Route path="/price" element={<AdminGuard><PageGuard page="/price"><Price /></PageGuard></AdminGuard>} />
              <Route path="/operacional" element={<PageGuard page="/operacional"><Operacional /></PageGuard>} />
              <Route path="/sac" element={<PageGuard page="/sac"><Sac /></PageGuard>} />
              <Route path="/engenharia" element={<PageGuard page="/engenharia"><Engenharia /></PageGuard>} />
              <Route path="/juridico" element={<PageGuard page="/juridico"><ComingSoon title="Jurídico" /></PageGuard>} />
              <Route path="/oraculo" element={<PageGuard page="/oraculo"><Oraculo /></PageGuard>} />
              <Route path="/admin/usuarios" element={<AdminGuard><Usuarios /></AdminGuard>} />
              <Route path="*" element={<Navigate to="/comercial" replace />} />
            </Routes>
          </Suspense>
        </Shell>
      </AuthProvider>
    </BrowserRouter>
  );
}
