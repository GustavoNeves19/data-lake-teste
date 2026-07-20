import { createContext, useContext, useMemo, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useMe, useLogout, type User } from "./api";
import { Spinner } from "../components/ui";
import { isPageHidden } from "./access";

// Contexto de autenticação: user (ou null se deslogado), estado de carregamento
// e função de logout já cabeada no hook do React Query.
interface AuthCtx {
  user: User | null;
  isLoading: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { data: user, isLoading } = useMe();
  const logoutMut = useLogout();

  const value = useMemo<AuthCtx>(
    () => ({
      user: user ?? null,
      isLoading,
      logout: () => logoutMut.mutate(),
    }),
    [user, isLoading, logoutMut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth deve ser usado dentro de <AuthProvider>");
  }
  return ctx;
}

// Guard padrão: protege rotas autenticadas. Enquanto carrega mostra spinner,
// se não houver usuário redireciona para /login preservando a rota de origem.
export function Guard({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="p-16">
        <Spinner label="Verificando sessão..." />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

// AdminGuard: restringe a admins. Não-admin volta pra /comercial.
export function AdminGuard({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="p-16">
        <Spinner label="Verificando permissões..." />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!user.is_admin) {
    return <Navigate to="/comercial" replace />;
  }
  return <>{children}</>;
}

export function PageGuard({
  page,
  children,
}: {
  page: string;
  children: ReactNode;
}) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="p-16">
        <Spinner label="Verificando permissões..." />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (isPageHidden(user, page)) {
    return (
      <div className="p-16">
        <h1 className="text-xl font-semibold text-gray-900 m-0">Acesso não liberado</h1>
        <p className="text-sm text-gray-500 mt-2 mb-0">
          Esta página não está habilitada para o seu usuário.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
