import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../lib/auth";
import { useTrocarSenha, ApiError } from "../lib/api";
import { NEVONI } from "../theme";

export default function TrocarSenha() {
  const { user } = useAuth();
  const trocar = useTrocarSenha();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErro(null);
    if (novaSenha.length < 8) {
      setErro("A nova senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    if (novaSenha !== confirmar) {
      setErro("A confirmação não bate com a nova senha.");
      return;
    }
    try {
      await trocar.mutateAsync({ senha_atual: senhaAtual, nova_senha: novaSenha });
      setSucesso(true);
      await qc.invalidateQueries({ queryKey: ["auth", "me"] });
      setTimeout(() => navigate("/", { replace: true }), 1200);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : "Não foi possível trocar a senha.");
    }
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center px-4 py-10" style={{ background: "#FBFAF7" }}>
      <div className="w-full max-w-[440px]">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1.5 text-[13px] mb-4 hover:underline"
          style={{ color: NEVONI.primary }}
        >
          <ArrowLeft size={14} /> Voltar
        </button>

        <div
          className="bg-white rounded-2xl px-8 py-8 border border-gray-200"
          style={{ boxShadow: "0 1px 2px rgba(20,15,80,0.04), 0 4px 16px rgba(20,15,80,0.05)" }}
        >
          <h2 className="text-[22px] font-semibold tracking-tight m-0" style={{ color: "#15151F" }}>
            Trocar senha
          </h2>
          <p className="text-[13px] mt-1 mb-6" style={{ color: "#6B7280" }}>
            {user?.nome ? `Olá, ${user.nome.split(" ")[0]}. ` : ""}Escolha uma senha só sua.
          </p>

          {sucesso && (
            <div
              role="status"
              className="mb-4 rounded-lg border px-3 py-2.5 text-sm flex items-center gap-2"
              style={{ background: "#ECFDF5", borderColor: "#A7F3D0", color: "#065F46" }}
            >
              <CheckCircle2 size={16} /> Senha atualizada. Voltando para o dashboard…
            </div>
          )}
          {erro && !sucesso && (
            <div
              role="alert"
              className="mb-4 rounded-lg border px-3 py-2.5 text-sm"
              style={{ background: "#FEF2F2", borderColor: "#FCA5A5", color: "#B91C1C" }}
            >
              {erro}
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            {(
              [
                { key: "senha_atual", label: "Senha atual", value: senhaAtual, setV: setSenhaAtual, autoComplete: "current-password" },
                { key: "nova_senha", label: "Nova senha", value: novaSenha, setV: setNovaSenha, autoComplete: "new-password" },
                { key: "confirmar", label: "Confirmar nova senha", value: confirmar, setV: setConfirmar, autoComplete: "new-password" },
              ] as const
            ).map((f) => (
              <label key={f.key} className="block">
                <span className="block text-[13px] font-medium mb-1.5" style={{ color: "#374151" }}>
                  {f.label}
                </span>
                <div className="relative">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "#9CA3AF" }} />
                  <input
                    type="password"
                    value={f.value}
                    onChange={(e) => f.setV(e.target.value)}
                    autoComplete={f.autoComplete}
                    required
                    placeholder="••••••••"
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
            ))}

            <button
              type="submit"
              disabled={trocar.isPending || sucesso || !senhaAtual || !novaSenha || !confirmar}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 text-[15px] font-semibold text-white mt-2 transition-[filter] disabled:opacity-60 disabled:cursor-not-allowed"
              style={{
                background: `linear-gradient(135deg, ${NEVONI.primary} 0%, #3A33B8 100%)`,
                boxShadow: "0 8px 20px rgba(30,24,130,0.24)",
              }}
              onMouseEnter={(e) => { if (!e.currentTarget.disabled) e.currentTarget.style.filter = "brightness(1.08)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.filter = "none"; }}
            >
              {trocar.isPending ? (<><Loader2 size={16} className="animate-spin" /> Salvando…</>) : "Salvar nova senha"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
