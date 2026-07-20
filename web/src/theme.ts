// Identidade visual Nevoni + config da Matriz RFV (porta de 02_Comercial_e_Compras.py).

export const NEVONI = {
  primary: "#1E1882",
  primaryDark: "#0D0B50",
  primaryLight: "#4844C8",
  pale: "#EEF0FF",
  gray: "#6B7280",
  success: "#10B981",
  warning: "#D97706",
  danger: "#DC2626",
};

// Paleta secundária para telas premium (login, capa, hero) — não substitui a marca.
export const GOLD = { main: "#C9A45A", deep: "#A8853F", pale: "#F5EEDC" };
export const NAVY_DEEP = "#0A1440";

export type Variant = "" | "success" | "warning" | "danger";

export const VARIANT_BORDER: Record<string, string> = {
  "": NEVONI.primary,
  success: NEVONI.success,
  warning: NEVONI.warning,
  danger: NEVONI.danger,
};

// Sombras reutilizáveis (Onda 1 — repouso visual sobre creme).
export const SHADOW = {
  card: "0 1px 2px rgba(20,15,80,0.04), 0 4px 16px rgba(20,15,80,0.03)",
  kpi: "0 1px 2px rgba(20,15,80,0.03)",
};

// ── Canais (Dashboard de Liderança) ───────────────────────────
export const ORDEM_CANAL = ["Hospitalar", "Marketplace", "Farmácias", "SAC", "Outros"] as const;

export const CANAL_COR: Record<string, string> = {
  Hospitalar: "#0D2B6B",
  Marketplace: "#0D8B92",
  Farmácias: "#7030A0",
  SAC: "#C55A11",
  Outros: "#6B7280",
};

export const CANAL_VISUAL: Record<string, { emoji: string; cor: string }> = {
  Hospitalar: { emoji: "🏥", cor: "#0D2B6B" },
  Marketplace: { emoji: "🛒", cor: "#0D8B92" },
  Farmácias: { emoji: "💊", cor: "#7030A0" },
  SAC: { emoji: "🛠", cor: "#C55A11" },
  Outros: { emoji: "📦", cor: "#6B7280" },
};

// Cores dos 3 períodos no gráfico comparativo
export const PERIODO_CORES = ["#1E1882", "#7A7AC8", "#B8B6E0"];

// ── Matriz RFV ────────────────────────────────────────────────
// seg_num -> apresentação. `area` = grid-area "rowStart / colStart / rowEnd / colEnd".
export interface SegDisplay {
  nome: string;
  area: string;
  bg: string;
  fg: string;
}

export const SEGMENT_DISPLAY: Record<number, SegDisplay> = {
  // Campeão = SÓ F1R1 (decisão Gustavo 10/07; gold mapeia só 'F1R1' -> seg 1).
  // Antes a célula abrangia F1+F2 (área ".../5/4") e "vazava" sobre o F2R1, que é
  // Fiéis. Agora é célula única F1R1; o F2R1 recebe o satélite de Fiéis abaixo.
  1: { nome: "Campeões", area: "3 / 3 / 4 / 4", bg: "#0D2B6B", fg: "#FFFFFF" },
  2: { nome: "Fiéis", area: "3 / 4 / 5 / 6", bg: "#0D8B92", fg: "#FFFFFF" },
  3: { nome: "Fiéis em potencial", area: "5 / 3 / 7 / 5", bg: "#B8CCE4", fg: "#000000" },
  4: { nome: "Novos clientes", area: "7 / 3 / 8 / 4", bg: "#92D050", fg: "#000000" },
  5: { nome: "Promessas", area: "7 / 4 / 8 / 5", bg: "#7030A0", fg: "#000000" },
  6: { nome: "Precisando de atenção", area: "5 / 5 / 6 / 6", bg: "#FFD966", fg: "#000000" },
  7: { nome: "Quase dormentes", area: "6 / 5 / 8 / 6", bg: "#FFC000", fg: "#000000" },
  8: { nome: "Não pode perder", area: "3 / 6 / 4 / 8", bg: "#D9E2F3", fg: "#000000" },
  9: { nome: "Em risco", area: "4 / 6 / 6 / 8", bg: "#F4C7AB", fg: "#000000" },
  10: { nome: "Hibernando", area: "6 / 6 / 7 / 7", bg: "#95A5C1", fg: "#000000" },
  11: { nome: "Perdidos", area: "7 / 6 / 8 / 8", bg: "#C55A11", fg: "#000000" },
};

// Ordem de render (Perdidos satélite vem antes pra não sobrepor)
export const SEG_RENDER_ORDER = [1, 2, 8, 9, 3, 6, 11, 10, 4, 5, 7];
export const PERDIDOS_SATELITE_AREA = "6 / 7 / 7 / 8";
// F2R1 é Fiéis (gold), mas fica separado do bloco principal de Fiéis; satélite
// preenche a célula com a cor de Fiéis, sem repetir o número (que fica no bloco).
export const FIEIS_SATELITE_AREA = "4 / 3 / 5 / 4";

// Cabeçalhos de recência (cols 3-7)
export const REC_HEADERS = [
  { code: "R1", desc: "Últimos 30 dias", bg: "#375623" },
  { code: "R2", desc: "Entre 31 e 60 dias", bg: "#5E8E3E" },
  { code: "R3", desc: "Entre 61 e 120 dias", bg: "#A9D18E" },
  { code: "R4", desc: "Entre 121 e 180 dias", bg: "#C6E0B4" },
  { code: "R5", desc: "Entre 181 e 360 dias", bg: "#E2F0D9" },
];

// Frequência (linhas 3-7) — bg por bucket
export const FREQ_BG: Record<string, string> = {
  F1: "#375623",
  F2: "#5E8E3E",
  F3: "#A9D18E",
  F4: "#C6E0B4",
  F5: "#E2F0D9",
};

// Descrição da frequência por família
export const FREQ_DESC: Record<string, Record<string, string>> = {
  HOSPITALAR: { F1: "5 vezes ou mais", F2: "Entre 4", F3: "Entre 3", F4: "Entre 2", F5: "1 vez" },
  FARMACIAS: { F1: "7 vezes ou mais", F2: "Entre 5 e 6", F3: "Entre 3 e 4", F4: "Entre 2", F5: "1 vez" },
  // Geral (TODOS) segue a régua do Hospitalar — metodologia oficial do Alves
  // (reunião 09/07). Antes ficava vazio e o eixo de frequência não tinha rótulo.
  TODOS: { F1: "5 vezes ou mais", F2: "Entre 4", F3: "Entre 3", F4: "Entre 2", F5: "1 vez" },
};

export const REGRA_FREQ: Record<string, string> = {
  HOSPITALAR: "Hospitalar: F1 = 5x ou mais, F2 = 4x, F3 = 3x, F4 = 2x, F5 = 1x.",
  FARMACIAS: "Farmácias: F1 = 7x ou mais, F2 = 5-6x, F3 = 3-4x, F4 = 2x, F5 = 1x.",
  TODOS: "Geral (régua do Hospitalar): F1 = 5x ou mais, F2 = 4x, F3 = 3x, F4 = 2x, F5 = 1x. Farmácias têm régua própria (use o filtro).",
};

// Glossário dos 11 segmentos
export const GLOSSARIO: { seg: number; nome: string; desc: string }[] = [
  { seg: 1, nome: "Campeões", desc: "F1 + R1. Compraram na maior frequência da família e tiveram a última compra nos últimos 30 dias." },
  { seg: 2, nome: "Fiéis", desc: "F1/F2 com recência entre 0 e 120 dias. Mantêm alta recorrência e já têm hábito de compra consistente." },
  { seg: 3, nome: "Fiéis em Potencial", desc: "F3/F4 em R1-R2. Compraram nos últimos 60 dias e estão próximos de virar Fiéis — manter contato para acelerar a segunda compra." },
  { seg: 4, nome: "Novos Clientes", desc: "F5 + R1. Fizeram 1 compra nos últimos 30 dias." },
  { seg: 5, nome: "Promessas", desc: "F5 + R2. Fizeram 1 compra há 31 a 60 dias e ainda não recompraram." },
  { seg: 6, nome: "Precisando de Atenção", desc: "F3 + R3. Estão entre 61 e 120 dias sem comprar e precisam de ação antes de migrar para risco." },
  { seg: 7, nome: "Quase Dormentes", desc: "F4/F5 + R3. Baixa recorrência e última compra entre 61 e 120 dias." },
  { seg: 8, nome: "Não Pode Perder", desc: "F1 + R4/R5. Eram muito recorrentes, mas estão entre 121 e 360 dias sem comprar." },
  { seg: 9, nome: "Em Risco", desc: "F2/F3 + R4/R5. Já estão há 121 a 360 dias sem compra e precisam de retomada urgente." },
  { seg: 10, nome: "Hibernando", desc: "F4 + R4. Baixa frequência e última compra há 121 a 180 dias." },
  { seg: 11, nome: "Perdidos", desc: "F4/F5 em R5, ou F5 em R4. Mais de 180 dias sem compra." },
];

export const SEG_OPTIONS: Record<number, string> = {
  1: "Campeões", 2: "Fiéis", 3: "Fiéis em Potencial", 4: "Novos Clientes",
  5: "Promessas", 6: "Precisando de Atenção", 7: "Quase Dormentes",
  8: "Não Pode Perder", 9: "Em Risco", 10: "Hibernando", 11: "Perdidos",
};

export const SEG_VARIANT: Record<number, Variant> = {
  1: "success", 2: "success", 3: "success", 4: "success", 5: "success",
  6: "warning", 7: "warning", 8: "warning", 9: "warning",
  10: "danger", 11: "danger",
};

// Alertas comerciais
export const ALERT_META: Record<string, { emoji: string; nome: string; variant: Variant; desc: string }> = {
  OPORTUNIDADE_SEM_CRM: { emoji: "🎯", nome: "Oportunidade sem CRM", variant: "warning", desc: "Clientes topo (Campeões/Fiéis/NPP) sem deal ativo no Pipedrive." },
  CHURN_SILENCIOSO: { emoji: "🔕", nome: "Churn Silencioso", variant: "danger", desc: "Em Risco/Hibernando sem deal e sem contato há 60d+." },
  RECUPERACAO_ANDAMENTO: { emoji: "🔄", nome: "Recuperação em Andamento", variant: "success", desc: "Em Risco/Hibernando com deal aberto, sinal positivo de reativação." },
  REATIVACAO_ALTO_VALOR: { emoji: "💰", nome: "Reativação Alto Valor", variant: "warning", desc: "Perdidos com faturamento histórico acima de R$ 50k." },
  FORA_DO_RADAR_CRM: { emoji: "📡", nome: "Fora do Radar CRM", variant: "danger", desc: "Clientes ativos no ERP sem correspondência no Pipedrive." },
};

// Status da validação QA
export const QA_VISUAL: Record<string, { icon: string; label: string; cor: string }> = {
  VERDE: { icon: "✅", label: "Validado", cor: "#16A34A" },
  AMARELO: { icon: "⚠️", label: "Atenção", cor: "#EAB308" },
  VERMELHO: { icon: "🔴", label: "Aguardando", cor: "#DC2626" },
};

// Cores das séries do painel por vendedor (stacked bar)
export const PAINEL_SERIES = [
  { key: "campeoes", nome: "Campeões", cor: "#0D5C4A" },
  { key: "fieis", nome: "Fiéis", cor: "#1B7A40" },
  { key: "fieis_potencial", nome: "Fiéis em Potencial", cor: "#4C9A5A" },
  { key: "nao_pode_perder", nome: "Não Pode Perder", cor: "#6D28D9" },
  { key: "em_risco_hibernando", nome: "Em Risco + Hibernando", cor: "#EA580C" },
  { key: "perdidos", nome: "Perdidos", cor: "#991B1B" },
] as const;
