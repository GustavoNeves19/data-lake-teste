import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// Base da API: vazio no dev (proxy do Vite trata /api); em produção defina
// VITE_API_BASE_URL com o domínio do backend.
const API_BASE = (import.meta.env as Record<string, string | undefined>).VITE_API_BASE_URL ?? "";

// Erro tipado que expõe o status HTTP (útil para tratar 401 sem parsear mensagem).
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// Alguns endpoints devolvem 204 No Content (ex: /api/auth/logout). Chamar
// res.json() nesses casos lança "Unexpected end of JSON input" e derruba o
// onSuccess das mutations. Este helper devolve undefined nesses casos.
async function parseBody<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const len = res.headers.get("content-length");
  if (len === "0") return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

async function parseError(res: Response): Promise<string> {
  let detail: unknown = res.statusText;
  try {
    const body = await res.json();
    detail = body.detail ?? detail;
  } catch { /* ignore */ }
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) return String(item.msg);
        return JSON.stringify(item);
      })
      .join("; ");
  }
  return JSON.stringify(detail);
}

async function get<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, { credentials: "include" });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  return parseBody<T>(res);
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  return parseBody<T>(res);
}

async function patch<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  return parseBody<T>(res);
}

async function put<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  return parseBody<T>(res);
}

async function del<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res));
  return parseBody<T>(res);
}

// ── Tipos ─────────────────────────────────────────────────────
export interface Opt { value: string; label: string; }

export interface VendasKpis {
  faturamento: number; fat_ant: number; fat_yoy: number;
  var_mom: number | null; var_yoy: number | null;
  ticket: number; transacoes: number;
  meta: number | null;
  projecao: number | null;
}
export interface PeriodoExato {
  de: string; ate: string; vendas_pedidos: number; faturamento_notas: number;
  pedidos: number; ticket: number;
  por_canal: { canal: string; pedidos: number; faturamento: number }[];
}
export interface CanalRow {
  canal: string; faturamento: number; fat_ant: number; fat_yoy: number;
  transacoes: number; ticket: number; var_mom: number | null; var_yoy: number | null;
}
export interface MarketplaceSubCanal {
  sub_canal: string; faturamento: number; transacoes: number; ticket: number;
  pct_marketplace: number;
}
export interface VendasData {
  empty: boolean;
  mes_ref: string; mes_ant: string; mes_ano_ant: string;
  label_ref: string; label_ant: string; label_yoy: string;
  kpis: VendasKpis;
  canais: CanalRow[];
  marketplace_detalhe: MarketplaceSubCanal[];
  evolucao: Record<string, number | string>[];
  total_mensal: { mes_label: string; faturamento: number; mom: number | null }[];
  semanas: Record<string, number | string>[];
}

export interface ComprasKpis {
  compras_dom: number; compras_dom_ordens: number;
  importacao_brl: number; importacao_usd: number;
  razao_compra_venda: number; concentracao_import: number;
  top_fornecedor_import: string;
}
export interface ComprasData {
  empty: boolean;
  kpis: ComprasKpis;
  serie: { mes_label: string; vendas: number; compras: number }[];
  import_fornecedores: { fornecedor: string; valor: number }[];
  top_fornecedores: { fornecedor: string; ordens: number; valor: number }[];
}
export interface OrcamentosKpis {
  pipeline_vivo: number; pipeline_n: number;
  parado: number; parado_n: number;
  conversao: number; ciclo: number | null;
}
export interface OrcamentosData {
  empty: boolean;
  kpis: OrcamentosKpis;
  conversao_safra: { mes: string; conv: number }[];
  aberto_idade: { idade: string; valor: number }[];
  parados: { cliente: string; dias_parado: number; valor: number }[];
}
export interface CrmData {
  empty: boolean;
  kpis: { total: number; abertos: number; ganhos: number; perdidos: number; taxa_ganho: number; pipeline_aberto: number; valor_ganho: number; win_rate_fechados: number; ciclo_medio: number | null; forecast_ponderado: number };
  stage_data: { stage_name: string; deals: number; valor: number }[];
  owner_data: { vendedor: string; deals: number; pipeline: number }[];
  deals_abertos: { pipeline: string; deal: string; estagio: string; vendedor: string; valor: number }[];
}
export interface RankingRow {
  posicao: number; cliente: string; city: string; state: string;
  qtd_pedidos: number; faturamento: number; classe: string; acum_pct: number;
}
export interface RankingData {
  empty: boolean;
  rows: RankingRow[];
  kpis: { top100_faturamento: number; classe_a: number; concentracao_top20: number };
}

// ── Gestão à Vista ────────────────────────────────────────────
export interface GvPipelineStats {
  stages: { nome: string; valor: number; n: number }[];
  pipe_open: number; win_rate: number | null; ticket_won: number | null;
}
export interface GvEngEtapa { cor: string; label: string; valor: number; caption: string; largura: number; }
export interface GvEngReversa {
  vazio: boolean; meta_tot?: number; ticket?: number; etapas?: GvEngEtapa[]; aprox?: boolean;
}
export interface GestaoVistaData {
  view: string; view_key: string; mes: string; mes_label: string; provisorio: boolean;
  meta: number; faturado_mes: number; pct_meta: number; falta: number;
  du_total: number; du_corr: number; du_rest: number;
  canais: { FA: number; FR: number; PC: number; MKT: number | null };
  ranking_mensal: { vendedor: string; realizado: number; meta: number | null; pct: number | null; ganho_crm: number; pct_crm: number | null }[];
  ranking_diario: { vendedor: string; vendido_hoje: number; meta_diaria: number | null; falta_hoje: number | null; bateu_hoje: boolean | null; pct_hoje: number | null; ganho_crm_hoje: number }[];
  vendedores: { vendedor: string; realizado: number; meta: number | null; pct: number | null }[];
  venda_necessaria_dia: { vendedor: string; venda_dia: number; batida: boolean }[];
  pipeline_hosp: GvPipelineStats; pipeline_farma: GvPipelineStats;
  eng_reversa_hosp: GvEngReversa; eng_reversa_farma: GvEngReversa;
  atividades_tipo: { tipo: string; concl: number; atras: number }[] | null;
  atividades_vendedor: { vendedor: string; concl: number; atras: number }[] | null;
  meses: Opt[];
}

// ── Calendário + Faturamento Mensal ──────────────────────────
export interface CalDia { day: number; value?: number; hit?: boolean | null; empty?: boolean; }
export interface CalWeek { cells: CalDia[]; week_total: number; }
export interface CalendarioData {
  titulo: string; mes: string; weeks: CalWeek[]; weekdays: string[];
  footer: {
    tem_meta: boolean; meta_dia: number; vendas: number; meta: number;
    rem_dia: number; dias_rest: number; rem_total: number; pct: number;
    du: number; du_corr: number;
    projecao: number; faturamento: number; fat_projecao: number;
  };
}
export interface FatCell { value: number; yoy_pct: number | null; future: boolean; }
export interface FatAcumCell { value: number; future: boolean; }
export interface FatPctCell { pct: number | null; future: boolean; }
export interface FatYear {
  year: number; values: FatCell[]; value_total: number;
  yoy_mes: FatPctCell[] | null; yoy_total: number | null;
  acum: FatAcumCell[]; yoy_acum: FatPctCell[] | null; tem_yoy: boolean;
}
export interface FaturamentoAnualData { months: string[]; years: FatYear[]; }

// ── Visão Geral (Monitor de Cargas) ──────────────────────────
export interface FrescorFonte {
  rotulo: string; table_id: string; modified_utc: string | null; modified_brt: string;
  idade_min: number | null; idade_txt: string; threshold_min: number; estado: string; cor: string;
}
export interface CadenciaCard { titulo: string; valor: string; sub: string; }
export interface RunResumo { fonte: string; ultima_carga: string; idade_min: number; idade_txt: string; cargas_hoje: number; }
export interface RunDetalhe { quando: string; fonte: string; entidade: string; status: string; linhas: number; segundos: number; }
export interface VisaoGeralData {
  header: { title: string; subtitle: string; sources: { name: string; active: boolean }[]; project: string };
  frescor: FrescorFonte[];
  cadencia: { cards: CadenciaCard[]; proxima_erp: string; proxima_crm: string; nota: string };
  runs_resumo: RunResumo[];
  runs_detalhe: RunDetalhe[];
  footer: string;
  erros: { runs_resumo: string | null; runs_detalhe: string | null };
}

// ── Financeiro ────────────────────────────────────────────────
export interface FinKpiCard { label: string; field: string; valor: number; mom_pct: number | null; dir: string; variant: string; }
export interface FinKpisData {
  ready: boolean; empty: boolean; regime: string; range: { ini: string; fim: string };
  mes_corrente_parcial?: boolean; cards: FinKpiCard[];
  serie: { mes: string; faturamento: number; margem_bruta: number; ebitda: number }[];
  serie_meta: { cores: Record<string, string> }; etl_loaded_at?: string | null;
}
export interface FinDreLinha { grupo_dre: string; descricao: string; valor: number; ordem: number; title_count: number; }
export interface FinDreData {
  ready: boolean; empty: boolean; regime: string; meses_disponiveis: string[];
  mes_selecionado?: string; linhas: FinDreLinha[]; pizza: { grupo_dre: string; valor: number }[];
}
export interface FinContasData {
  ready: boolean; empty: boolean;
  resumo: { total: number; titulos: number; vencido: number; pct_vencido: number; pct_variant: string };
  por_vencimento: { mes: string; valor: number }[];
  titulos_sample: { title_number: string; partner_name: string; vencimento: string; valor: number; group_name: string; subgroup: string }[];
}
export interface FinLiqData {
  ready: boolean; empty: boolean; resumo: { total_liquidado: number; qtd: number };
  por_mes: { mes: string; tipo_liquidacao: string; valor_liquidado: number; qtd: number }[];
}
export interface FinFluxoData {
  ready: boolean; empty: boolean;
  resumo: { saldo_acumulado: number; saldo_ultimo_mes: number; saldo_ultimo_variant: string };
  por_mes: { mes: string; entradas: number; saidas: number; saldo: number }[];
}

// ── SAC ───────────────────────────────────────────────────────
export interface SacAtendimentos {
  camada: string; empty: boolean;
  kpis: { total_atendimentos: number; resolvidos: number; taxa_resolucao_pct: number; tmr_medio_h: number; abertos: number };
  por_mes: { mes: string; qtd: number; tmr_horas: number }[];
  por_status: { status: string; qtd: number }[];
  por_pipeline: { pipeline_id: number; rotulo: string; qtd: number }[];
}
export interface SacSla {
  camada_crm: string; camada_chat: string;
  kpis: { tmr_resolucao_ultimo_mes_h: number; tmr_resolucao_medio_h: number; t_primeira_resposta_mediana_min: number | null };
  tmr_resolucao_por_mes: { mes: string; tmr_horas: number; qtd: number }[];
  primeira_resposta_por_mes: { mes: string; mediana_min: number; qtd_chats_sac: number }[];
  meta_h: number;
}
export interface SacChamadas {
  camada: string; empty: boolean;
  janela: { de: string | null; ate: string | null; aviso: string };
  kpis: { total_chamadas: number; minutos_total: number; duracao_media_min: number };
  por_mes: { mes: string; qtd: number; minutos: number }[];
  por_direcao: { direcao: string; qtd: number }[];
  por_sentimento: { sentimento: string; qtd: number }[];
}
export interface SacChat {
  camada: string; empty: boolean; filtro?: string;
  kpis: { total_conversas_sac: number; canais: number; abertas: number };
  por_mes: { mes: string; canal: string; conversas: number }[];
  por_canal: { canal: string; conversas: number }[];
}

// ── Operacional ───────────────────────────────────────────────
export interface OpProducao {
  camada: string; empty: boolean;
  kpis: { total_ops: number; qtd_planejada: number; qtd_produzida: number; eficiencia_global: number };
  planejado_produzido: { mes: string; qtd_op: number; qtd_planejada: number; qtd_produzida: number }[];
  por_status: { prod_status: number; status_label: string; qtd_op: number }[];
}
export interface OpComponentes {
  camada: string; empty: boolean;
  componentes: { item_code: string; item_nome: string; consumido: number; planejado: number }[];
}
export interface OpEstoque {
  camada: string; empty: boolean;
  kpis: { itens: number; total_qtd: number; grupos: number };
  itens: { item_code: string; item_nome: string; group_name: string; saldo: number }[];
  por_grupo: { group_name: string; saldo: number }[];
}
export interface OpMovimentacao {
  camada: string; empty: boolean;
  series: { mes: string; entradas: number; saidas: number }[];
}
export interface OpBom {
  camada: string; empty: boolean;
  kpis: { produtos_com_bom: number; relacoes: number };
  linhas: { parent_item_code: string; produto_pai: string; child_item_code: string; componente: string; quantity: number }[];
  produtos_pai: string[];
}

// ── Engenharia ────────────────────────────────────────────────
export interface EngCatalogo {
  kpis: { total_skus: number; ativos: number; familias: number | null; grupos: number };
  mix_grupo: { group_name: string; qtd: number }[];
  familias_disponivel: boolean; avisos: string[];
}
export interface EngItem {
  item_code: string; item_name: string; group_name: string;
  unit_code: number | null; net_weight: number; gross_weight: number; is_active: boolean;
}
export interface EngItens { total: number; page: number; page_size: number; itens: EngItem[]; }
export interface EngBomLinha {
  parent_item_code: string; produto_pai: string; child_item_code: string;
  componente: string; quantity: number; link_type: string; link_label: string;
}
export interface EngBom {
  kpis: { produtos_com_bom: number; relacoes_bom: number };
  produtos: string[]; linhas: EngBomLinha[];
}
export interface EngExplosao {
  item_code: string | null;
  niveis: { nivel: number; child_item_code: string; componente: string; quantity: number; path: string }[];
}
export interface EngSeriais {
  itens: { item_code: string; item_name: string; total_seriais: number; em_uso: number; lotes: number }[];
}
export interface EngRoadmap {
  status: string; titulo: string; mensagem: string; kpis_planejados: string[]; fontes_a_integrar: string[];
}

// ── Oráculo (IA) ──────────────────────────────────────────────
export interface OraculoMsg { role: string; content: string; }
export interface OraculoResp {
  answer: string; rows: Record<string, unknown>[];
  truncated?: boolean; debug_sql?: string | null; ok: boolean;
}

export interface QaRow { escopo: string; status: string; delta: number; }
export interface RfvKpi {
  total_clientes: number; campeoes: number; fieis: number; fp: number;
  nao_pode_perder: number; em_risco: number; perdidos: number;
  faturamento: number; data_referencia: string | null;
}
export interface RfvCell {
  freq_bucket: string; rec_bucket: string; segmento: string;
  seg_num: number; clientes: number; faturamento: number;
}
export interface RfvSegment { seg_num: number; segmento: string; clientes: number; faturamento: number; }
export interface PainelRow {
  vendedor: string; clientes: number; campeoes: number; fieis: number;
  fieis_potencial: number; nao_pode_perder: number; em_risco_hibernando: number; perdidos: number;
  faturamento: number; ticket_medio: number; crm_deals: number; pipeline_crm: number;
  alertas_oportunidade: number; alertas_churn: number; clientes_fora_radar: number;
}
export interface AlertaRow { tipo_alerta: string; qtd: number; valor_total: number; }
export interface RfvData {
  kpi: RfvKpi; cells: RfvCell[]; segments: RfvSegment[];
  painel: PainelRow[]; alertas: AlertaRow[];
}
// ── Matriz de Performance (Esforço x Resultado) ────────────────
export interface PerformanceDetalhe {
  ligacoes: number; reunioes: number; propostas: number; followups: number;
  atividades_registradas: number; oportunidades_criadas: number; ciclo_medio_dias: number | null;
  receita_realizada: number; receita_contratada: number; meta: number | null; meta_atingida_pct: number;
  pipeline_gerado: number; conversao_pct: number; ticket_medio: number;
}
export interface PerformanceVendedor {
  vendedor: string; esforco_score: number; resultado_score: number; quadrante: string;
  detalhe: PerformanceDetalhe;
}
export interface PerformanceData {
  mes: string; mes_label: string; vazio: boolean; vendedores: PerformanceVendedor[];
}

export interface SegmentoDetalhe {
  rows: { nome_cliente: string; familia: string; vendedor: string; ultima_compra: string; dias_sem_comprar: number; frequencia: number; valor_total: number }[];
  qtd: number; faturamento: number; ticket: number;
}
export interface AlertaDetalhe {
  rows: { cliente: string; familias: string; filiais: number; vendedores: string; segmentos: string; faturamento: number; deals_abertos: number; pipeline_crm: number; dias_sem_deal: number; no_crm: string; org_pipedrive: string; descricao: string }[];
  qtd: number; faturamento: number; ticket: number;
}

// ── Hooks ─────────────────────────────────────────────────────
const HOUR = 60 * 60 * 1000;
const opts = { staleTime: HOUR, gcTime: HOUR };

export const useMeses = () =>
  useQuery({ queryKey: ["meses"], queryFn: () => get<Opt[]>("/api/comercial/meses"), ...opts });

export const useVendas = (mes: string | undefined, incluirMarketplace = true) =>
  useQuery({ queryKey: ["vendas", mes, incluirMarketplace], queryFn: () => get<VendasData>(`/api/comercial/vendas?mes=${mes}&incluir_marketplace=${incluirMarketplace}`), enabled: !!mes, ...opts });

export const useVendasPeriodo = (de: string | undefined, ate: string | undefined) =>
  useQuery({ queryKey: ["vendas_periodo", de, ate], queryFn: () => get<PeriodoExato>(`/api/comercial/vendas/periodo?de=${de}&ate=${ate}`), enabled: !!de && !!ate, ...opts });

export const useCompras = () =>
  useQuery({ queryKey: ["compras"], queryFn: () => get<ComprasData>("/api/comercial/compras"), ...opts });

export const useGestaoVistaMeses = () =>
  useQuery({ queryKey: ["gv_meses"], queryFn: () => get<Opt[]>("/api/comercial/gestao-vista/meses"), ...opts });

// refetchMs > 0 liga o auto-refresh (usado pelo Modo TV, que fica ligado o dia todo).
export interface AtividadesPeriodoData {
  atividades_tipo: { tipo: string; concl: number; atras: number }[] | null;
  atividades_vendedor: { vendedor: string; concl: number; atras: number }[] | null;
}
export const useAtividadesPeriodo = (de: string | undefined, ate: string | undefined) =>
  useQuery({
    queryKey: ["gv_atividades", de, ate],
    queryFn: () => get<AtividadesPeriodoData>(`/api/comercial/gestao-vista/atividades?de=${de}&ate=${ate}`),
    enabled: !!de && !!ate,
    ...opts,
  });

export const useGestaoVista = (view: string, mes: string | undefined, refetchMs = 0, vendedor = "") =>
  useQuery({
    queryKey: ["gestao_vista", view, mes, vendedor],
    queryFn: () => get<GestaoVistaData>(`/api/comercial/gestao-vista?view=${encodeURIComponent(view)}${mes ? `&mes=${mes}` : ""}${vendedor ? `&vendedor=${encodeURIComponent(vendedor)}` : ""}`),
    enabled: !!mes,
    ...opts,
    ...(refetchMs > 0 ? { refetchInterval: refetchMs, staleTime: 0 } : {}),
  });

export const useCalendario = (mes: string | undefined) =>
  useQuery({ queryKey: ["calendario", mes], queryFn: () => get<CalendarioData>(`/api/comercial/calendario?mes=${mes}`), enabled: !!mes, ...opts });

export const useFaturamentoAnual = () =>
  useQuery({ queryKey: ["faturamento_anual"], queryFn: () => get<FaturamentoAnualData>("/api/comercial/faturamento-anual"), ...opts });

export const usePerformance = (mes: string | undefined) =>
  useQuery({ queryKey: ["performance", mes], queryFn: () => get<PerformanceData>(`/api/comercial/performance${mes ? `?mes=${mes}` : ""}`), ...opts });

// Monitor de Cargas: cache curto + auto-refresh (é uma tela viva).
export const useVisaoGeral = () =>
  useQuery({ queryKey: ["visao_geral"], queryFn: () => get<VisaoGeralData>("/api/visao-geral"), staleTime: 60000, gcTime: 60000, refetchInterval: 60000 });

// ── Financeiro ────────────────────────────────────────────────
const finRange = (ini?: string, fim?: string) =>
  `${ini ? `&ini=${ini}` : ""}${fim ? `&fim=${fim}` : ""}`;

export const useFinKpis = (regime: string, ini?: string, fim?: string) =>
  useQuery({ queryKey: ["fin_kpis", regime, ini, fim], queryFn: () => get<FinKpisData>(`/api/financeiro/kpis?regime=${regime}${finRange(ini, fim)}`), ...opts });

export const useFinDre = (regime: string, ini?: string, fim?: string, mes?: string) =>
  useQuery({ queryKey: ["fin_dre", regime, ini, fim, mes], queryFn: () => get<FinDreData>(`/api/financeiro/dre?regime=${regime}${finRange(ini, fim)}${mes ? `&mes=${mes}` : ""}`), ...opts });

export const useFinContasReceber = () =>
  useQuery({ queryKey: ["fin_cr"], queryFn: () => get<FinContasData>("/api/financeiro/contas-receber"), ...opts });

export const useFinContasPagar = () =>
  useQuery({ queryKey: ["fin_cp"], queryFn: () => get<FinContasData>("/api/financeiro/contas-pagar"), ...opts });

export const useFinLiquidacoes = () =>
  useQuery({ queryKey: ["fin_liq"], queryFn: () => get<FinLiqData>("/api/financeiro/liquidacoes"), ...opts });

export const useFinFluxo = () =>
  useQuery({ queryKey: ["fin_fluxo"], queryFn: () => get<FinFluxoData>("/api/financeiro/fluxo-caixa"), ...opts });

// ── SAC ───────────────────────────────────────────────────────
export const useSacAtendimentos = () =>
  useQuery({ queryKey: ["sac_atend"], queryFn: () => get<SacAtendimentos>("/api/sac/atendimentos"), ...opts });
export const useSacSla = () =>
  useQuery({ queryKey: ["sac_sla"], queryFn: () => get<SacSla>("/api/sac/sla"), ...opts });
export const useSacChamadas = () =>
  useQuery({ queryKey: ["sac_chamadas"], queryFn: () => get<SacChamadas>("/api/sac/chamadas"), ...opts });
export const useSacChat = () =>
  useQuery({ queryKey: ["sac_chat"], queryFn: () => get<SacChat>("/api/sac/chat"), ...opts });

// ── Operacional ───────────────────────────────────────────────
export const useOpProducao = () =>
  useQuery({ queryKey: ["op_prod"], queryFn: () => get<OpProducao>("/api/operacional/producao"), ...opts });
export const useOpComponentes = () =>
  useQuery({ queryKey: ["op_comp"], queryFn: () => get<OpComponentes>("/api/operacional/componentes"), ...opts });
export const useOpEstoque = () =>
  useQuery({ queryKey: ["op_estoque"], queryFn: () => get<OpEstoque>("/api/operacional/estoque"), ...opts });
export const useOpMovimentacao = () =>
  useQuery({ queryKey: ["op_mov"], queryFn: () => get<OpMovimentacao>("/api/operacional/movimentacao"), ...opts });
export const useOpBom = (parent?: string) =>
  useQuery({ queryKey: ["op_bom", parent], queryFn: () => get<OpBom>(`/api/operacional/bom${parent ? `?parent=${encodeURIComponent(parent)}` : ""}`), ...opts });

// ── Engenharia ────────────────────────────────────────────────
export const useEngCatalogo = () =>
  useQuery({ queryKey: ["eng_cat"], queryFn: () => get<EngCatalogo>("/api/engenharia/catalogo"), ...opts });
export const useEngItens = (q: string, page: number, pageSize = 50) =>
  useQuery({ queryKey: ["eng_itens", q, page, pageSize], queryFn: () => get<EngItens>(`/api/engenharia/catalogo/itens?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`), ...opts });
export const useEngBom = (itemCode?: string) =>
  useQuery({ queryKey: ["eng_bom", itemCode], queryFn: () => get<EngBom>(`/api/engenharia/bom${itemCode ? `?item_code=${encodeURIComponent(itemCode)}` : ""}`), ...opts });
export const useEngExplosao = (itemCode: string | undefined) =>
  useQuery({ queryKey: ["eng_expl", itemCode], queryFn: () => get<EngExplosao>(`/api/engenharia/bom/explosao?item_code=${encodeURIComponent(itemCode!)}`), enabled: !!itemCode, ...opts });
export const useEngSeriais = (itemCode?: string) =>
  useQuery({ queryKey: ["eng_ser", itemCode], queryFn: () => get<EngSeriais>(`/api/engenharia/seriais${itemCode ? `?item_code=${encodeURIComponent(itemCode)}` : ""}`), ...opts });
export const useEngRoadmap = () =>
  useQuery({ queryKey: ["eng_roadmap"], queryFn: () => get<EngRoadmap>("/api/engenharia/roadmap"), ...opts });

// ── Oráculo (IA) ──────────────────────────────────────────────
export const useOraculoReady = () =>
  useQuery({ queryKey: ["oraculo_ready"], queryFn: () => get<{ ready: boolean }>("/api/oraculo/ready"), staleTime: 300000, gcTime: 300000 });

export const useOraculoChat = () =>
  useMutation({
    mutationFn: (payload: { message: string; history: OraculoMsg[] }) =>
      post<OraculoResp>("/api/oraculo/chat", payload),
  });

export const useOrcamentos = () =>
  useQuery({ queryKey: ["orcamentos"], queryFn: () => get<OrcamentosData>("/api/comercial/orcamentos"), ...opts });

export const useCrmPipelines = () =>
  useQuery({ queryKey: ["crm_pipelines"], queryFn: () => get<string[]>("/api/comercial/crm/pipelines"), ...opts });

export const useCrm = (pipeline: string) =>
  useQuery({ queryKey: ["crm", pipeline], queryFn: () => get<CrmData>(`/api/comercial/crm?pipeline=${encodeURIComponent(pipeline)}`), ...opts });

export const useRanking = () =>
  useQuery({ queryKey: ["ranking"], queryFn: () => get<RankingData>("/api/comercial/ranking"), ...opts });

export const useQa = () =>
  useQuery({ queryKey: ["qa"], queryFn: () => get<QaRow[]>("/api/comercial/qa"), ...opts });

export const useRfvPeriodos = () =>
  useQuery({ queryKey: ["rfv_periodos"], queryFn: () => get<Opt[]>("/api/comercial/rfv/periodos"), ...opts });

export const useRfvCarteiras = (familia: string, periodo: string | undefined) =>
  useQuery({ queryKey: ["rfv_carteiras", familia, periodo], queryFn: () => get<{ value: string; label: string }[]>(`/api/comercial/rfv/carteiras?familia=${familia}${periodo ? `&periodo=${periodo}` : ""}`), ...opts });

export const useRfv = (familia: string, carteira: string, periodo: string | undefined) =>
  useQuery({ queryKey: ["rfv", familia, carteira, periodo], queryFn: () => get<RfvData>(`/api/comercial/rfv?familia=${familia}&carteira=${encodeURIComponent(carteira)}${periodo ? `&periodo=${periodo}` : ""}`), ...opts });

export const useRfvSegmento = (seg: number, familia: string, carteira: string, periodo: string | undefined) =>
  useQuery({ queryKey: ["rfv_seg", seg, familia, carteira, periodo], queryFn: () => get<SegmentoDetalhe>(`/api/comercial/rfv/segmento?seg=${seg}&familia=${familia}&carteira=${encodeURIComponent(carteira)}${periodo ? `&periodo=${periodo}` : ""}`), enabled: !!seg, ...opts });

export const useRfvAlerta = (tipo: string | undefined, familia: string) =>
  useQuery({ queryKey: ["rfv_alerta", tipo, familia], queryFn: () => get<AlertaDetalhe>(`/api/comercial/rfv/alerta?tipo=${tipo}&familia=${familia}`), enabled: !!tipo, ...opts });

// ── Auth / Users ─────────────────────────────────────────────
export interface User {
  id: number;
  email: string;
  nome: string;
  is_admin: boolean;
  pode_editar_metas: boolean;
  pode_usar_oraculo: boolean;
  paginas_ocultas: string[];
  recursos_ocultos: string[];
  paginas_liberadas?: string[] | null;
  recursos_liberados?: string[] | null;
  precisa_trocar_senha: boolean;
}

export interface AdminUser extends User {
  is_active: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
}

export interface MetaEquipe {
  mes: string;
  view_key: string;
  meta: number;
  updated_by?: string | null;
  updated_at?: string | null;
}

// useMe: verifica sessão atual. Retorna null em 401 (usuário deslogado).
// retry:false para não ficar batendo em /me durante navegação de rota /login.
export const useMe = () =>
  useQuery({
    queryKey: ["auth", "me"],
    queryFn: async (): Promise<User | null> => {
      try {
        const res = await get<{ user: User }>("/api/auth/me");
        return res.user;
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

export const useLogin = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; password: string }) =>
      post<{ user: User }>("/api/auth/login", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
};

export const useLogout = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post<{ ok: boolean }>("/api/auth/logout", {}),
    onSuccess: () => {
      qc.clear();
      window.location.href = "/login";
    },
  });
};

export const useTrocarSenha = () =>
  useMutation({
    mutationFn: (payload: { senha_atual: string; nova_senha: string }) =>
      post<{ ok: boolean }>("/api/auth/trocar-senha", payload),
  });

// Admin — gestão de usuários (só is_admin, senão 403)
export const useAdminUsers = () =>
  useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => get<AdminUser[]>("/api/admin/users"),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });

export const useAdminCreateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      email: string;
      nome: string;
      senha_inicial: string;
      is_admin: boolean;
      pode_editar_metas: boolean;
      pode_usar_oraculo: boolean;
      paginas_ocultas: string[];
      recursos_ocultos: string[];
      paginas_liberadas?: string[] | null;
      recursos_liberados?: string[] | null;
    }) => post<AdminUser>("/api/admin/users", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
};

export const useAdminUpdateUser = (id: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      nome?: string;
      is_admin?: boolean;
      pode_editar_metas?: boolean;
      pode_usar_oraculo?: boolean;
      paginas_ocultas?: string[];
      recursos_ocultos?: string[];
      paginas_liberadas?: string[] | null;
      recursos_liberados?: string[] | null;
      is_active?: boolean;
      resetar_senha?: { nova_senha: string };
    }) => patch<AdminUser>(`/api/admin/users/${id}`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
};

export const useAdminDeleteUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => del<{ ok: boolean }>(`/api/admin/users/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
};

// Metas de equipe (Gestão à Vista)
export const useMetasEquipe = () =>
  useQuery({
    queryKey: ["metas_equipe"],
    queryFn: () => get<MetaEquipe[]>("/api/comercial/metas-equipe"),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });

export const useSalvarMeta = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { mes: string; view_key: string; meta: number }) =>
      put<MetaEquipe>("/api/comercial/metas-equipe", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["metas_equipe"] });
      qc.invalidateQueries({ queryKey: ["gestao_vista"] });
    },
  });
};

// ── PRICE (lucro líquido por produto × canal) ─────────────────
export interface PriceRow {
  item_code: string;
  item_name: string;
  canal: string;
  n_pedidos: number;
  quantidade: number;
  faturamento: number;
  ticket_medio: number;
  imposto_icms: number;
  imposto_ipi: number;
  custo_pecas: number;
  mao_obra: number;
  imposto_nota: number;
  despesas: number;
  imposto_lucro: number;
  custo_total: number;
  margem: number;
  margem_pct: number | null;
  custo_peca: number;
  custo_manual: boolean;
  custo_travado_erp: boolean;
  pct_ads: number;
  pct_comissao: number;
  pct_irpj_csll: number;
  pct_irpj: number;
  pct_csll: number;
  pct_pis: number;
  pct_cofins: number;
  pct_credito_icms_ipi: number;
  pct_credito_icms: number;
  pct_credito_ipi: number;
  mao_obra_unit: number;
  pct_custo_fixo: number;
  pct_outras: number;
}

export interface PriceData {
  mes: string;
  empty: boolean;
  rows: PriceRow[];
  totais: { faturamento: number; margem: number; margem_pct: number | null; n_itens: number };
}

export interface PriceUfRow extends PriceRow {
  uf: string;
}

export interface PriceUfData {
  mes: string;
  item_code: string;
  canal: string;
  rows: PriceUfRow[];
}

export interface PriceCustoPayload {
  item_code: string;
  canal: string;
  mes: string;
  custo_peca: number | null;
  pct_ads: number | null;
  pct_comissao: number | null;
  pct_irpj_csll: number | null;
  pct_irpj: number | null;
  pct_csll: number | null;
  pct_pis: number | null;
  pct_cofins: number | null;
  pct_credito_icms_ipi: number | null;
  pct_credito_icms: number | null;
  pct_credito_ipi: number | null;
  mao_obra_unit: number | null;
  pct_custo_fixo: number | null;
  pct_outras: number | null;
}

export const usePriceMeses = () =>
  useQuery({
    queryKey: ["price_meses"],
    queryFn: () => get<Opt[]>("/api/price/meses"),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });

export const usePrice = (mes: string | undefined) =>
  useQuery({
    queryKey: ["price", mes],
    queryFn: () => get<PriceData>(`/api/price?mes=${mes}`),
    enabled: !!mes,
    ...opts,
  });

export const usePriceUf = (mes: string | undefined, itemCode: string | undefined, canal: string | undefined) =>
  useQuery({
    queryKey: ["price_uf", mes, itemCode, canal],
    queryFn: () => get<PriceUfData>(
      `/api/price/uf?mes=${mes}&item_code=${encodeURIComponent(itemCode!)}&canal=${encodeURIComponent(canal!)}`,
    ),
    enabled: !!mes && !!itemCode && !!canal,
    ...opts,
  });

export const useSalvarPriceCusto = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: PriceCustoPayload) => put<{ ok: boolean }>("/api/price/custo", payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["price"] });
    },
  });
};
