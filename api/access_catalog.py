"""Catalogo tecnico de paginas, abas e rotas API controladas por acesso."""

PAGINAS_CONTROLADAS = {
    "/visao-geral",
    "/comercial",
    "/compras",
    "/financeiro",
    "/price",
    "/operacional",
    "/sac",
    "/engenharia",
    "/juridico",
    "/oraculo",
}

RESOURCE_ACCESS_GROUPS = {
    "/comercial": {
        "comercial:vendas",
        "comercial:gestao-vista",
        "comercial:rfv",
        "comercial:performance",
    },
    "/financeiro": {
        "financeiro:kpis",
        "financeiro:dre",
        "financeiro:contas-receber",
        "financeiro:contas-pagar",
        "financeiro:liquidacoes",
        "financeiro:fluxo-caixa",
    },
    "/sac": {
        "sac:atendimentos",
        "sac:sla",
        "sac:chamadas",
        "sac:chat",
    },
    "/operacional": {
        "operacional:producao",
        "operacional:estoque",
        "operacional:bom",
    },
    "/engenharia": {
        "engenharia:catalogo",
        "engenharia:bom",
        "engenharia:roadmap",
    },
}

RECURSOS_CONTROLADOS = {
    recurso
    for recursos in RESOURCE_ACCESS_GROUPS.values()
    for recurso in recursos
}

API_PAGE_ACCESS = [
    ("/api/visao-geral", "/visao-geral"),
    ("/api/financeiro", "/financeiro"),
    ("/api/price", "/price"),
    ("/api/sac", "/sac"),
    ("/api/operacional", "/operacional"),
    ("/api/engenharia", "/engenharia"),
    ("/api/oraculo", "/oraculo"),
    ("/api/comercial/compras", "/compras"),
    ("/api/comercial", "/comercial"),
]

API_RESOURCE_ACCESS = [
    ("/api/comercial/vendas/periodo", "comercial:vendas"),
    ("/api/comercial/vendas", "comercial:vendas"),
    ("/api/comercial/calendario", "comercial:vendas"),
    ("/api/comercial/faturamento-anual", "comercial:vendas"),
    ("/api/comercial/gestao-vista", "comercial:gestao-vista"),
    ("/api/comercial/metas-equipe", "comercial:gestao-vista"),
    ("/api/comercial/rfv", "comercial:rfv"),
    ("/api/comercial/performance", "comercial:performance"),
    ("/api/financeiro/kpis", "financeiro:kpis"),
    ("/api/financeiro/dre", "financeiro:dre"),
    ("/api/financeiro/contas-receber", "financeiro:contas-receber"),
    ("/api/financeiro/contas-pagar", "financeiro:contas-pagar"),
    ("/api/financeiro/liquidacoes", "financeiro:liquidacoes"),
    ("/api/financeiro/fluxo-caixa", "financeiro:fluxo-caixa"),
    ("/api/sac/atendimentos", "sac:atendimentos"),
    ("/api/sac/sla", "sac:sla"),
    ("/api/sac/chamadas", "sac:chamadas"),
    ("/api/sac/chat", "sac:chat"),
    ("/api/operacional/producao", "operacional:producao"),
    ("/api/operacional/componentes", "operacional:producao"),
    ("/api/operacional/estoque", "operacional:estoque"),
    ("/api/operacional/movimentacao", "operacional:estoque"),
    ("/api/operacional/bom", "operacional:bom"),
    ("/api/engenharia/catalogo", "engenharia:catalogo"),
    ("/api/engenharia/seriais", "engenharia:bom"),
    ("/api/engenharia/bom", "engenharia:bom"),
    ("/api/engenharia/roadmap", "engenharia:roadmap"),
]
