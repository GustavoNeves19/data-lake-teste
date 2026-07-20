import { useMemo, useState } from "react";
import { PageHeader } from "../components/layout";
import {
  Card,
  DataTable,
  Spinner,
  ErrorBox,
  type Column,
} from "../components/ui";
import {
  useAdminUsers,
  useAdminCreateUser,
  useAdminUpdateUser,
  useAdminDeleteUser,
  type AdminUser,
} from "../lib/api";
import {
  DEFAULT_HIDDEN_PAGES,
  DEFAULT_HIDDEN_RESOURCES,
  PAGE_ACCESS_OPTIONS,
  RESOURCE_ACCESS_GROUPS,
} from "../lib/accessCatalog";
import { useAuth } from "../lib/auth";

// ── Toast simples (sem dependência externa) ───────────────────
function useToast() {
  const [msg, setMsg] = useState<string | null>(null);
  const show = (m: string) => {
    setMsg(m);
    window.setTimeout(() => setMsg(null), 6000);
  };
  const node = msg ? (
    <div
      className="fixed bottom-6 right-6 z-50 max-w-sm rounded-lg bg-[#1E1882] text-white px-4 py-3 text-sm shadow-lg"
      style={{ boxShadow: "0 6px 20px rgba(20,15,80,0.25)" }}
    >
      {msg}
    </div>
  ) : null;
  return { show, node };
}

// ── Modal reutilizável ────────────────────────────────────────
function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <h2 className="text-[17px] font-bold text-gray-900 m-0">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Fechar"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ── Campos de formulário ──────────────────────────────────────
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium text-gray-600">{label}</span>
      {children}
    </label>
  );
}

function TextInput(
  props: React.InputHTMLAttributes<HTMLInputElement>,
) {
  return (
    <input
      {...props}
      className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800
                 focus:outline-none focus:ring-2 focus:ring-[#1E1882]/30 focus:border-[#1E1882]"
    />
  );
}

function Checkbox({
  label,
  checked,
  onChange,
  disabled = false,
  variant = "plain",
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  variant?: "plain" | "pill";
}) {
  if (variant === "pill") {
    return (
      <label
        className={`flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm transition-colors
          ${checked ? "border-[#1E1882]/30 bg-white text-gray-900" : "border-gray-200 bg-gray-100 text-gray-500"}
          ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:border-[#1E1882]/45"}`}
      >
        <span className="min-w-0 truncate">{label}</span>
        <span
          className={`relative h-5 w-9 shrink-0 rounded-full transition-colors
            ${checked ? "bg-[#1E1882]" : "bg-gray-300"}`}
        >
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            className="sr-only"
          />
          <span
            className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform
              ${checked ? "translate-x-4" : "translate-x-0.5"}`}
          />
        </span>
      </label>
    );
  }

  return (
    <label className={`flex items-center gap-2 text-sm text-gray-700 ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="h-4 w-4 rounded border-gray-300 text-[#1E1882] focus:ring-[#1E1882]/30"
      />
      {label}
    </label>
  );
}

function PageAccessCheckboxes({
  hiddenPages,
  onChange,
}: {
  hiddenPages: string[];
  onChange: (pages: string[]) => void;
}) {
  const toggle = (path: string, canAccess: boolean) => {
    if (canAccess) {
      onChange(hiddenPages.filter((p) => p !== path));
      return;
    }
    onChange([...new Set([...hiddenPages, path])]);
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Páginas
          </div>
          <div className="text-sm font-semibold text-gray-900">
            Acesso principal do usuário
          </div>
        </div>
        <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-gray-500 ring-1 ring-gray-200">
          {PAGE_ACCESS_OPTIONS.length - hiddenPages.length}/{PAGE_ACCESS_OPTIONS.length} liberadas
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {PAGE_ACCESS_OPTIONS.map((page) => (
          <Checkbox
            key={page.path}
            label={page.label}
            checked={!hiddenPages.includes(page.path)}
            onChange={(v) => toggle(page.path, v)}
            variant="pill"
          />
        ))}
      </div>
    </div>
  );
}

function ResourceAccessCheckboxes({
  hiddenResources,
  hiddenPages,
  onChange,
}: {
  hiddenResources: string[];
  hiddenPages: string[];
  onChange: (resources: string[]) => void;
}) {
  const toggle = (resource: string, canAccess: boolean) => {
    if (canAccess) {
      onChange(hiddenResources.filter((r) => r !== resource));
      return;
    }
    onChange([...new Set([...hiddenResources, resource])]);
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Abas internas
          </div>
          <div className="text-sm font-semibold text-gray-900">
            Detalhamento por módulo
          </div>
        </div>
        <span className="rounded-full bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-500 ring-1 ring-gray-200">
          V1 por aba
        </span>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
      {RESOURCE_ACCESS_GROUPS.map((group) => {
        const disabled = hiddenPages.includes(group.page);
        const total = group.resources.length;
        const blocked = group.resources.filter((resource) => hiddenResources.includes(resource.key)).length;
        return (
          <div
            key={group.page}
            className={`rounded-lg border p-3 transition-colors
              ${disabled ? "border-gray-200 bg-gray-50 opacity-60" : "border-gray-200 bg-gray-50"}`}
          >
            <div className="mb-3 flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-semibold text-gray-900">
                  {group.label.replace("Abas do ", "").replace("Abas da ", "")}
                </div>
                <div className="text-[11px] text-gray-500">
                  {disabled ? "Página bloqueada" : `${total - blocked}/${total} abas liberadas`}
                </div>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium
                  ${disabled ? "bg-gray-200 text-gray-500" : blocked ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700"}`}
              >
                {disabled ? "Inativo" : blocked ? "Parcial" : "Completo"}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {group.resources.map((resource) => (
                <Checkbox
                  key={resource.key}
                  label={resource.label}
                  checked={!hiddenResources.includes(resource.key)}
                  onChange={(v) => toggle(resource.key, v)}
                  disabled={disabled}
                  variant="pill"
                />
              ))}
            </div>
          </div>
        );
      })}
      </div>
    </div>
  );
}

// ── Botão padrão ──────────────────────────────────────────────
function PrimaryButton({
  children,
  onClick,
  disabled,
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg bg-[#1E1882] text-white px-4 py-2 text-sm font-semibold
                 hover:bg-[#2C28A8] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      {children}
    </button>
  );
}

function GhostButton({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg border border-gray-300 bg-white text-gray-700 px-4 py-2 text-sm font-medium
                 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      {children}
    </button>
  );
}

// ── Estado do formulário de usuário ───────────────────────────
interface UserFormState {
  email: string;
  nome: string;
  senha_inicial: string;
  is_admin: boolean;
  pode_editar_metas: boolean;
  pode_usar_oraculo: boolean;
  paginas_ocultas: string[];
  recursos_ocultos: string[];
}

const emptyForm: UserFormState = {
  email: "",
  nome: "",
  senha_inicial: "",
  is_admin: false,
  pode_editar_metas: false,
  pode_usar_oraculo: false,
  paginas_ocultas: DEFAULT_HIDDEN_PAGES,
  recursos_ocultos: DEFAULT_HIDDEN_RESOURCES,
};

const newEmptyForm = (): UserFormState => ({
  ...emptyForm,
  paginas_ocultas: [...DEFAULT_HIDDEN_PAGES],
  recursos_ocultos: [...DEFAULT_HIDDEN_RESOURCES],
});

const ALL_PAGE_PATHS = PAGE_ACCESS_OPTIONS.map((page) => page.path);
const ALL_RESOURCE_KEYS = RESOURCE_ACCESS_GROUPS.flatMap((group) =>
  group.resources.map((resource) => resource.key),
);

function hiddenToAllowed(hidden: string[], all: string[]) {
  return all.filter((item) => !hidden.includes(item));
}

function allowedToHidden(allowed: string[] | null | undefined, fallbackHidden: string[], all: string[]) {
  if (!Array.isArray(allowed)) return fallbackHidden;
  return all.filter((item) => !allowed.includes(item));
}

function gerarSenhaTemporaria() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const bytes = new Uint8Array(10);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => alphabet[byte % alphabet.length]).join("");
}

function Badge({ on }: { on: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium
        ${on ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"}`}
    >
      {on ? "Sim" : "Não"}
    </span>
  );
}

// ── Página ────────────────────────────────────────────────────
export default function Usuarios() {
  const { data: users, isLoading, error } = useAdminUsers();
  const createMut = useAdminCreateUser();
  const deleteMut = useAdminDeleteUser();
  useAuth(); // garante contexto de sessão presente
  const toast = useToast();

  // Modais e seleção
  const [novoOpen, setNovoOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [desativarOpen, setDesativarOpen] = useState(false);

  const [form, setForm] = useState<UserFormState>(emptyForm);
  const [selected, setSelected] = useState<AdminUser | null>(null);
  const [formErro, setFormErro] = useState<string | null>(null);

  // useAdminUpdateUser é fabricado por id; instanciamos sob o usuário selecionado
  // (id=0 quando ninguém está selecionado — a mutação só dispara com selected != null).
  const updateMut = useAdminUpdateUser(selected?.id ?? 0);

  function abrirNovo() {
    setForm(newEmptyForm());
    setFormErro(null);
    setNovoOpen(true);
  }

  function abrirEditar(u: AdminUser) {
    setSelected(u);
    setForm({
      email: u.email,
      nome: u.nome,
      senha_inicial: "",
      is_admin: u.is_admin,
      pode_editar_metas: u.pode_editar_metas,
      pode_usar_oraculo: u.pode_usar_oraculo,
      paginas_ocultas: allowedToHidden(u.paginas_liberadas, u.paginas_ocultas ?? [], ALL_PAGE_PATHS),
      recursos_ocultos: allowedToHidden(u.recursos_liberados, u.recursos_ocultos ?? [], ALL_RESOURCE_KEYS),
    });
    setFormErro(null);
    setEditOpen(true);
  }

  function abrirReset(u: AdminUser) {
    setSelected(u);
    setFormErro(null);
    setResetOpen(true);
  }

  function abrirDesativar(u: AdminUser) {
    setSelected(u);
    setDesativarOpen(true);
  }

  async function submitNovo(e: React.FormEvent) {
    e.preventDefault();
    setFormErro(null);
    if (!form.email.trim() || !form.nome.trim() || !form.senha_inicial.trim()) {
      setFormErro("Preencha e-mail, nome e senha inicial.");
      return;
    }
    try {
      await createMut.mutateAsync({
        email: form.email.trim(),
        nome: form.nome.trim(),
        senha_inicial: form.senha_inicial,
        is_admin: form.is_admin,
        pode_editar_metas: form.pode_editar_metas,
        pode_usar_oraculo: form.pode_usar_oraculo,
        paginas_ocultas: form.paginas_ocultas,
        recursos_ocultos: form.recursos_ocultos,
        paginas_liberadas: hiddenToAllowed(form.paginas_ocultas, ALL_PAGE_PATHS),
        recursos_liberados: hiddenToAllowed(form.recursos_ocultos, ALL_RESOURCE_KEYS),
      });
      setNovoOpen(false);
      toast.show(
        `Passe a senha para ${form.nome.trim()} pessoalmente. Ele vai precisar trocar no primeiro login.`,
      );
    } catch (err) {
      setFormErro((err as Error).message);
    }
  }

  async function submitEditar(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setFormErro(null);
    try {
      await updateMut.mutateAsync({
        nome: form.nome.trim(),
        is_admin: form.is_admin,
        pode_editar_metas: form.pode_editar_metas,
        pode_usar_oraculo: form.pode_usar_oraculo,
        paginas_ocultas: form.paginas_ocultas,
        recursos_ocultos: form.recursos_ocultos,
        paginas_liberadas: hiddenToAllowed(form.paginas_ocultas, ALL_PAGE_PATHS),
        recursos_liberados: hiddenToAllowed(form.recursos_ocultos, ALL_RESOURCE_KEYS),
      });
      setEditOpen(false);
      toast.show(`Alterações salvas para ${form.nome.trim()}.`);
    } catch (err) {
      setFormErro((err as Error).message);
    }
  }

  async function confirmarReset() {
    if (!selected) return;
    setFormErro(null);
    try {
      const novaSenha = gerarSenhaTemporaria();
      await updateMut.mutateAsync({ resetar_senha: { nova_senha: novaSenha } });
      const nome = selected.nome;
      window.alert(`Nova senha temporaria de ${nome}: ${novaSenha}`);
      setResetOpen(false);
      toast.show(
        `Nova senha gerada para ${nome}. Combine com ele pessoalmente e peça pra trocar no primeiro login.`,
      );
    } catch (err) {
      setFormErro((err as Error).message);
    }
  }

  async function confirmarDesativar() {
    if (!selected) return;
    try {
      await deleteMut.mutateAsync(selected.id);
      const nome = selected.nome;
      setDesativarOpen(false);
      toast.show(`${nome} foi desativado.`);
    } catch (err) {
      toast.show((err as Error).message);
    }
  }

  // ── Colunas da tabela ───────────────────────────────────────
  const columns: Column<AdminUser>[] = useMemo(
    () => [
      { key: "nome", header: "Nome" },
      { key: "email", header: "E-mail" },
      {
        key: "is_admin",
        header: "Admin",
        align: "center",
        render: (r) => <Badge on={r.is_admin} />,
      },
      {
        key: "pode_editar_metas",
        header: "Edita metas",
        align: "center",
        render: (r) => <Badge on={r.pode_editar_metas} />,
      },
      {
        key: "pode_usar_oraculo",
        header: "Oráculo",
        align: "center",
        render: (r) => <Badge on={r.pode_usar_oraculo} />,
      },
      {
        key: "paginas_ocultas",
        header: "Páginas",
        render: (r) => {
          const hiddenPages = allowedToHidden(r.paginas_liberadas, r.paginas_ocultas ?? [], ALL_PAGE_PATHS);
          const hiddenResources = allowedToHidden(r.recursos_liberados, r.recursos_ocultos ?? [], ALL_RESOURCE_KEYS);
          const totalPaginas = hiddenPages.length;
          const totalRecursos = hiddenResources.length;
          return (
            <span className="text-xs text-gray-600">
              {totalPaginas === 0 ? "Todas" : `${totalPaginas} página${totalPaginas > 1 ? "s" : ""} bloqueada${totalPaginas > 1 ? "s" : ""}`}
              {totalRecursos > 0 ? ` · ${totalRecursos} aba${totalRecursos > 1 ? "s" : ""}` : ""}
            </span>
          );
        },
      },
      {
        key: "is_active",
        header: "Ativo",
        align: "center",
        render: (r) => <Badge on={r.is_active} />,
      },
      {
        key: "acoes",
        header: "Ações",
        align: "right",
        render: (r) => (
          <div className="flex justify-end gap-2 flex-wrap">
            <button
              onClick={() => abrirEditar(r)}
              className="text-[12px] font-medium text-[#1E1882] hover:underline"
            >
              Editar
            </button>
            <button
              onClick={() => abrirReset(r)}
              className="text-[12px] font-medium text-[#1E1882] hover:underline"
            >
              Resetar senha
            </button>
            {r.is_active && (
              <button
                onClick={() => abrirDesativar(r)}
                className="text-[12px] font-medium text-red-600 hover:underline"
              >
                Desativar
              </button>
            )}
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <div className="p-6 md:p-8">
      <PageHeader
        title="Usuários"
        subtitle="Cadastre a equipe e defina o que cada pessoa pode fazer"
      />

      <div className="flex justify-end mb-4">
        <PrimaryButton onClick={abrirNovo}>+ Novo usuário</PrimaryButton>
      </div>

      <Card>
        {isLoading && <Spinner label="Carregando usuários…" />}
        {error && <ErrorBox message={(error as Error).message} />}
        {users && users.length === 0 && (
          <p className="text-sm text-gray-500 py-4 text-center">
            Nenhum usuário cadastrado ainda.
          </p>
        )}
        {users && users.length > 0 && (
          <DataTable columns={columns} rows={users} />
        )}
      </Card>

      {/* Modal: novo usuário */}
      <Modal
        open={novoOpen}
        onClose={() => setNovoOpen(false)}
        title="Novo usuário"
      >
        <form onSubmit={submitNovo} className="flex flex-col gap-3">
          <Field label="E-mail">
            <TextInput
              type="email"
              value={form.email}
              onChange={(e) =>
                setForm({ ...form, email: e.target.value })
              }
              autoFocus
              required
            />
          </Field>
          <Field label="Nome">
            <TextInput
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              required
            />
          </Field>
          <Field label="Senha inicial">
            <TextInput
              type="text"
              value={form.senha_inicial}
              onChange={(e) =>
                setForm({ ...form, senha_inicial: e.target.value })
              }
              required
            />
          </Field>
          <div className="flex flex-col gap-2 pt-2">
            <Checkbox
              label="Admin"
              checked={form.is_admin}
              onChange={(v) => setForm({ ...form, is_admin: v })}
            />
            <Checkbox
              label="Pode editar metas"
              checked={form.pode_editar_metas}
              onChange={(v) => setForm({ ...form, pode_editar_metas: v })}
            />
            <Checkbox
              label="Pode usar Oráculo"
              checked={form.pode_usar_oraculo}
              onChange={(v) => setForm({ ...form, pode_usar_oraculo: v })}
            />
          </div>
          <PageAccessCheckboxes
            hiddenPages={form.paginas_ocultas}
            onChange={(paginas_ocultas) => setForm({ ...form, paginas_ocultas })}
          />
          <ResourceAccessCheckboxes
            hiddenResources={form.recursos_ocultos}
            hiddenPages={form.paginas_ocultas}
            onChange={(recursos_ocultos) => setForm({ ...form, recursos_ocultos })}
          />
          {formErro && <ErrorBox message={formErro} />}
          <div className="flex justify-end gap-2 pt-3">
            <GhostButton onClick={() => setNovoOpen(false)}>
              Cancelar
            </GhostButton>
            <PrimaryButton type="submit" disabled={createMut.isPending}>
              {createMut.isPending ? "Criando…" : "Criar usuário"}
            </PrimaryButton>
          </div>
        </form>
      </Modal>

      {/* Modal: editar usuário */}
      <Modal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        title={`Editar ${selected?.nome ?? ""}`}
      >
        <form onSubmit={submitEditar} className="flex flex-col gap-3">
          <Field label="E-mail">
            <TextInput
              type="email"
              value={form.email}
              disabled
              readOnly
            />
          </Field>
          <Field label="Nome">
            <TextInput
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              required
            />
          </Field>
          <div className="flex flex-col gap-2 pt-2">
            <Checkbox
              label="Admin"
              checked={form.is_admin}
              onChange={(v) => setForm({ ...form, is_admin: v })}
            />
            <Checkbox
              label="Pode editar metas"
              checked={form.pode_editar_metas}
              onChange={(v) => setForm({ ...form, pode_editar_metas: v })}
            />
            <Checkbox
              label="Pode usar Oráculo"
              checked={form.pode_usar_oraculo}
              onChange={(v) => setForm({ ...form, pode_usar_oraculo: v })}
            />
          </div>
          <PageAccessCheckboxes
            hiddenPages={form.paginas_ocultas}
            onChange={(paginas_ocultas) => setForm({ ...form, paginas_ocultas })}
          />
          <ResourceAccessCheckboxes
            hiddenResources={form.recursos_ocultos}
            hiddenPages={form.paginas_ocultas}
            onChange={(recursos_ocultos) => setForm({ ...form, recursos_ocultos })}
          />
          {formErro && <ErrorBox message={formErro} />}
          <div className="flex justify-end gap-2 pt-3">
            <GhostButton onClick={() => setEditOpen(false)}>
              Cancelar
            </GhostButton>
            <PrimaryButton type="submit" disabled={updateMut.isPending}>
              {updateMut.isPending ? "Salvando…" : "Salvar"}
            </PrimaryButton>
          </div>
        </form>
      </Modal>

      {/* Modal: resetar senha */}
      <Modal
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        title={`Resetar senha de ${selected?.nome ?? ""}`}
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-gray-700 m-0">
            O sistema vai gerar uma nova senha temporária. Combine com{" "}
            {selected?.nome ?? "o usuário"} pessoalmente e ele será obrigado a
            trocá-la no próximo login.
          </p>
          {formErro && <ErrorBox message={formErro} />}
          <div className="flex justify-end gap-2 pt-3">
            <GhostButton onClick={() => setResetOpen(false)}>
              Cancelar
            </GhostButton>
            <PrimaryButton
              onClick={confirmarReset}
              disabled={updateMut.isPending}
            >
              {updateMut.isPending ? "Resetando…" : "Resetar senha"}
            </PrimaryButton>
          </div>
        </div>
      </Modal>

      {/* Modal: desativar */}
      <Modal
        open={desativarOpen}
        onClose={() => setDesativarOpen(false)}
        title={`Desativar ${selected?.nome ?? ""}?`}
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-gray-700 m-0">
            O usuário perderá acesso imediatamente, mas o histórico é
            preservado. Você pode reativá-lo depois.
          </p>
          <div className="flex justify-end gap-2 pt-3">
            <GhostButton onClick={() => setDesativarOpen(false)}>
              Cancelar
            </GhostButton>
            <button
              type="button"
              onClick={confirmarDesativar}
              disabled={deleteMut.isPending}
              className="rounded-lg bg-red-600 text-white px-4 py-2 text-sm font-semibold
                         hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {deleteMut.isPending ? "Desativando…" : "Desativar"}
            </button>
          </div>
        </div>
      </Modal>

      {toast.node}
    </div>
  );
}
