import type { User } from "./api";
import { isResourceHidden } from "./access";

export type AccessPage = {
  path: string;
  label: string;
};

export type AccessResource = {
  id: string;
  key: string;
  label: string;
};

export type AccessResourceGroup = {
  page: string;
  label: string;
  resources: AccessResource[];
};

export const PAGE_ACCESS_OPTIONS: AccessPage[] = [
  { path: "/visao-geral", label: "Visão Geral" },
  { path: "/comercial", label: "Vendas" },
  { path: "/compras", label: "Compras" },
  { path: "/financeiro", label: "Financeiro" },
  { path: "/price", label: "PRICE" },
  { path: "/operacional", label: "Operacional e Produção" },
  { path: "/sac", label: "SAC e AT" },
  { path: "/engenharia", label: "Engenharia e P&D" },
  { path: "/juridico", label: "Jurídico" },
  { path: "/oraculo", label: "Oráculo" },
];

export const DEFAULT_HIDDEN_PAGES = PAGE_ACCESS_OPTIONS.map((page) => page.path);

export const RESOURCE_ACCESS_GROUPS: AccessResourceGroup[] = [
  {
    page: "/comercial",
    label: "Abas de Vendas",
    resources: [
      { id: "vendas", key: "comercial:vendas", label: "Vendas" },
      { id: "gestao", key: "comercial:gestao-vista", label: "Gestão à Vista" },
      { id: "rfv", key: "comercial:rfv", label: "Matriz RFV" },
      { id: "performance", key: "comercial:performance", label: "Performance" },
    ],
  },
  {
    page: "/financeiro",
    label: "Abas do Financeiro",
    resources: [
      { id: "kpis", key: "financeiro:kpis", label: "📈 KPIs" },
      { id: "dre", key: "financeiro:dre", label: "📋 DRE" },
      { id: "cr", key: "financeiro:contas-receber", label: "📥 Contas a Receber" },
      { id: "cp", key: "financeiro:contas-pagar", label: "📤 Contas a Pagar" },
      { id: "liq", key: "financeiro:liquidacoes", label: "💵 Liquidações" },
      { id: "fluxo", key: "financeiro:fluxo-caixa", label: "🌊 Fluxo de Caixa" },
    ],
  },
  {
    page: "/sac",
    label: "Abas do SAC e AT",
    resources: [
      { id: "atendimentos", key: "sac:atendimentos", label: "🎫 Atendimentos" },
      { id: "sla", key: "sac:sla", label: "⏱️ SLA" },
      { id: "chamadas", key: "sac:chamadas", label: "📞 Chamadas" },
      { id: "chat", key: "sac:chat", label: "💬 Chat" },
    ],
  },
  {
    page: "/operacional",
    label: "Abas do Operacional",
    resources: [
      { id: "producao", key: "operacional:producao", label: "🏭 Ordens de Produção" },
      { id: "estoque", key: "operacional:estoque", label: "📦 Estoque" },
      { id: "bom", key: "operacional:bom", label: "🧬 BOM" },
    ],
  },
  {
    page: "/engenharia",
    label: "Abas da Engenharia",
    resources: [
      { id: "catalogo", key: "engenharia:catalogo", label: "📦 Catálogo de Produtos" },
      { id: "bom", key: "engenharia:bom", label: "🧬 Estrutura Técnica (BOM)" },
      { id: "roadmap", key: "engenharia:roadmap", label: "🔬 Roadmap P&D" },
    ],
  },
];

export const DEFAULT_HIDDEN_RESOURCES = RESOURCE_ACCESS_GROUPS.flatMap((group) =>
  group.resources.map((resource) => resource.key),
);

export function getPageResourceTabs(page: string) {
  return (
    RESOURCE_ACCESS_GROUPS.find((group) => group.page === page)?.resources.map((resource) => ({
      id: resource.id,
      label: resource.label,
      resource: resource.key,
    })) ?? []
  );
}

export function getVisiblePageTabs(page: string, user: User | null | undefined) {
  return getPageResourceTabs(page)
    .filter((tab) => !isResourceHidden(user, tab.resource))
    .map(({ id, label }) => ({ id, label }));
}
