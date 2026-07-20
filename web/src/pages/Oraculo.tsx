import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useOraculoReady, useOraculoChat, type OraculoMsg } from "../lib/api";
import { Spinner } from "../components/ui";

const PROSE_ORACULO_CSS = `
.prose-oraculo { color: #15151F; font-size: 14px; line-height: 1.55; }
.prose-oraculo p { margin: 0 0 10px 0; }
.prose-oraculo p:last-child { margin-bottom: 0; }
.prose-oraculo strong { font-weight: 600; color: #1E1882; }
.prose-oraculo em { font-style: italic; }
.prose-oraculo ul, .prose-oraculo ol { margin: 6px 0 10px 20px; padding: 0; }
.prose-oraculo li { margin: 3px 0; }
.prose-oraculo h1, .prose-oraculo h2, .prose-oraculo h3 { font-size: 15px; font-weight: 600; color: #111827; margin: 12px 0 6px; }
.prose-oraculo a { color: #1E1882; text-decoration: underline; }
.prose-oraculo code { background: #F4F5FB; padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
.prose-oraculo table { border-collapse: collapse; font-size: 12.5px; margin-top: 8px; }
.prose-oraculo th, .prose-oraculo td { padding: 5px 10px; border-bottom: 1px solid #F0F0F5; text-align: left; }
.prose-oraculo th { background: #F8F9FE; color: #6B7280; font-weight: 600; text-transform: uppercase; font-size: 10.5px; letter-spacing: 0.06em; }
`;

interface ChatMsg { role: "user" | "assistant"; content: string; rows?: Record<string, unknown>[]; }

const EXEMPLOS = [
  "Quantos clientes Campeões temos no Hospitalar?",
  "Qual o faturamento do último mês fechado?",
  "Quais clientes estão em risco de churn?",
  "Top 5 clientes por faturamento no período",
];

export default function Oraculo() {
  const ready = useOraculoReady();
  const chat = useOraculoChat();
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);

  const enviar = (texto: string) => {
    const pergunta = texto.trim();
    if (!pergunta || chat.isPending) return;
    const history: OraculoMsg[] = msgs.map((m) => ({ role: m.role, content: m.content }));
    setMsgs((m) => [...m, { role: "user", content: pergunta }]);
    setInput("");
    chat.mutate(
      { message: pergunta, history },
      {
        onSuccess: (r) =>
          setMsgs((m) => [...m, { role: "assistant", content: r.answer, rows: r.rows }]),
        onError: (e) =>
          setMsgs((m) => [...m, { role: "assistant", content: `Erro: ${(e as Error).message}` }]),
      },
    );
  };

  return (
    <div className="max-w-[900px] mx-auto px-6 py-6">
      <style dangerouslySetInnerHTML={{ __html: PROSE_ORACULO_CSS }} />
      {/* Header */}
      <div
        className="rounded-2xl text-white px-7 py-5 mb-4"
        style={{ background: "linear-gradient(135deg, #1E1882 0%, #4A3FD0 100%)", borderBottom: "3px solid #10B981" }}
      >
        <h1 className="text-[22px] font-bold m-0 mb-1">Oráculo</h1>
        <p className="text-[13px] text-white/70 m-0">
          Pergunte em português. A IA cuida do resto.
        </p>
      </div>

      {ready.isLoading ? (
        <Spinner label="Verificando o Oráculo…" />
      ) : ready.data && !ready.data.ready ? (
        <div className="rounded-xl px-5 py-4 text-sm" style={{ background: "#FEF3E2", color: "#8A5A00" }}>
          ⚠️ O Oráculo está indisponível no momento. Fale com o time de dados para reativar.
        </div>
      ) : (
        <>
          {/* Boas-vindas / exemplos */}
          {msgs.length === 0 && (
            <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-4">
              <p className="text-sm text-gray-600 mb-3">Os dados estão prontos. Experimente perguntar:</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {EXEMPLOS.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => enviar(ex)}
                    className="text-left text-sm rounded-lg border border-gray-200 px-3 py-2 hover:border-[#1E1882] hover:bg-[#EEF0FF] transition-colors"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Conversa */}
          <div className="flex flex-col gap-3 mb-4">
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "self-end max-w-[85%]" : "self-start max-w-[95%]"}>
                {m.role === "user" ? (
                  <div
                    className="rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap"
                    style={{ background: "#1E1882", color: "#fff" }}
                  >
                    {m.content}
                  </div>
                ) : (
                  <div
                    className="rounded-2xl px-4 py-3 text-sm"
                    style={{ background: "#fff", border: "1px solid #ECECF3", color: "#15151F" }}
                  >
                    <div className="prose-oraculo">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                    </div>
                    {m.rows && m.rows.length > 0 && <RowsTable rows={m.rows} />}
                  </div>
                )}
              </div>
            ))}
            {chat.isPending && (
              <div className="self-start">
                <div className="rounded-2xl px-4 py-3 bg-white border border-gray-200">
                  <Spinner label="Consultando os dados…" />
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="sticky bottom-4 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") enviar(input); }}
              placeholder="Pergunte ao Oráculo…"
              className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#1E1882]"
            />
            <button
              onClick={() => enviar(input)}
              disabled={chat.isPending || !input.trim()}
              className="rounded-xl px-5 py-3 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "#1E1882" }}
            >
              Enviar
            </button>
          </div>

          <p className="text-[11px] text-gray-400 mt-2 text-center">
            O Oráculo pode responder sem consultar os dados. Para números oficiais, use as abas validadas
            (Comercial, Gestão à Vista, Financeiro).
          </p>
        </>
      )}
    </div>
  );
}

function RowsTable({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = Object.keys(rows[0] ?? {});
  if (cols.length === 0) return null;
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c} className="text-left px-2 py-1 bg-[#F8F9FE] text-gray-600 font-semibold border-b border-gray-200">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 20).map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c} className="px-2 py-1 border-b border-gray-100 tabular-nums">{String(r[c] ?? "—")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
