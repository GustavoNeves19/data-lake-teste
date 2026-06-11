"""
Mapa canônico das tabelas Gold — única fonte de verdade do dashboard.
O dashboard NÃO acessa raw (dm_*) nem silver (*). Tudo vem daqui.

Convenção de nomes:
  gold_<setor>.<tabela>   (todos lowercase, snake_case)

Adicione novas tabelas aqui conforme forem criadas no BigQuery.
"""

from dashboard.utils.bq_client import PROJECT_PROD as _PROJ

# ── Datasets Gold por setor ───────────────────────────────────────────
_G = {
    "fin":  f"{_PROJ}.gold_financeiro",
    "com":  f"{_PROJ}.gold_comercial",
    "ops":  f"{_PROJ}.gold_operacional",
    "fis":  f"{_PROJ}.gold_fiscal",
    "sac":  f"{_PROJ}.gold_sac",
    "jur":  f"{_PROJ}.gold_juridico",
    "eng":  f"{_PROJ}.gold_engenharia",
}

# ═══════════════════════════════════════════════════════════════════════
# FINANCEIRO
# ═══════════════════════════════════════════════════════════════════════
class Financeiro:
    # Grain: regime (caixa|competencia) × grupo_dre × mes
    DRE_MENSAL          = f"{_G['fin']}.gold_fin_dre_mensal"
    # Grain: mes (indicadores consolidados)
    KPIS_MENSAIS        = f"{_G['fin']}.gold_fin_kpis_mensais"
    # Grain: titulo × vencimento
    CONTAS_RECEBER      = f"{_G['fin']}.contas_receber"
    # Grain: titulo × vencimento
    CONTAS_PAGAR        = f"{_G['fin']}.contas_pagar"
    # Grain: categoria_fluxo × mes
    FLUXO_CAIXA         = f"{_G['fin']}.fluxo_caixa"
    # Grain: mes × tipo_liquidacao
    LIQUIDACOES_MENSAIS = f"{_G['fin']}.liquidacoes_mensais"
    # Parâmetro: indicador × mes (metas Diego)
    METAS_MENSAIS       = f"{_G['fin']}.param_metas_mensais"

# ═══════════════════════════════════════════════════════════════════════
# COMERCIAL E COMPRAS
# ═══════════════════════════════════════════════════════════════════════
class Comercial:
    # Grain: mes × empresa
    VENDAS_MENSAIS      = f"{_G['com']}.vendas_mensais"
    # Grain: mes × empresa
    COMPRAS_MENSAIS     = f"{_G['com']}.compras_mensais"
    # Grain: mes × status
    ORCAMENTOS_MENSAIS  = f"{_G['com']}.orcamentos_mensais"
    # Grain: cliente × mes (top N)
    RANKING_CLIENTES    = f"{_G['com']}.ranking_clientes"
    # Grain: pipeline × estagio × mes (CRM deals)
    FUNIL_CRM           = f"{_G['com']}.funil_crm"
    # Grain: mes (taxa de conversão orçamento→pedido)
    CONVERSAO_ORC       = f"{_G['com']}.conversao_orcamento"

    # ── RFV (produção em gold_comercial + silver_comercial) ───────────
    # Grain: partner_name × rfv_familia (score RFV completo)
    RFV_SCORE           = f"{_PROJ}.silver_comercial.silver_com_rfv_score"
    # Grain: rfv_familia × rfv_salesperson × segmento (resumo)
    RFV_RESUMO          = f"{_PROJ}.silver_comercial.silver_com_rfv_resumo"
    # Grain: partner_code (visão 360: RFV + CRM + alertas)
    CLIENTE_360         = f"{_G['com']}.gold_com_cliente_360"
    # Grain: partner_code × tipo_alerta
    ALERTA_COMERCIAL    = f"{_G['com']}.gold_com_alerta_comercial"
    # Grain: rfv_salesperson × rfv_familia (painel KPI)
    VENDEDOR_PAINEL     = f"{_G['com']}.gold_com_vendedor_painel"
    # Grain: pipeline_id × stage_id × status
    PIPELINE_CRM        = f"{_G['com']}.gold_com_pipeline_crm"

# ═══════════════════════════════════════════════════════════════════════
# OPERACIONAL E PRODUÇÃO
# ═══════════════════════════════════════════════════════════════════════
class Operacional:
    # Grain: mes × item
    PRODUCAO_MENSAL     = f"{_G['ops']}.producao_mensal"
    # Grain: mes × linha (eficiência OPs)
    EFICIENCIA          = f"{_G['ops']}.eficiencia_linhas"
    # Grain: item_code (saldo atual)
    ESTOQUE_SNAPSHOT    = f"{_G['ops']}.estoque_snapshot"
    # Grain: familia × mes
    GIRO_ESTOQUE        = f"{_G['ops']}.giro_estoque"
    # Grain: mes (entradas vs saídas)
    MOVIMENTACAO_MENSAL = f"{_G['ops']}.movimentacao_mensal"

# ═══════════════════════════════════════════════════════════════════════
# FISCAL
# ═══════════════════════════════════════════════════════════════════════
class Fiscal:
    # Grain: tipo_imposto × mes
    IMPOSTOS_MENSAIS    = f"{_G['fis']}.impostos_mensais"
    # Grain: mes × pais_origem
    IMPORTACOES_MENSAIS = f"{_G['fis']}.importacoes_mensais"
    # Grain: produto × mes
    CARGA_TRIBUTARIA    = f"{_G['fis']}.carga_tributaria"

# ═══════════════════════════════════════════════════════════════════════
# SAC E ASSISTÊNCIA TÉCNICA
# ═══════════════════════════════════════════════════════════════════════
class SAC:
    # Grain: mes × canal × pipeline
    ATENDIMENTOS_MENSAIS = f"{_G['sac']}.atendimentos_mensais"
    # Grain: mes (TMR, TMPR, taxa resolução)
    SLA_MENSAL           = f"{_G['sac']}.sla_mensal"
    # Grain: mes × direção × resultado
    CHAMADAS_MENSAIS     = f"{_G['sac']}.chamadas_mensais"
    # Grain: mes × canal (Umbler chat + e-mail)
    CHAT_MENSAIS         = f"{_G['sac']}.chat_mensais"

# ═══════════════════════════════════════════════════════════════════════
# JURÍDICO E HOMOLOGAÇÕES
# ═══════════════════════════════════════════════════════════════════════
class Juridico:
    HOMOLOGACOES        = f"{_G['jur']}.homologacoes"
    CONTRATOS_ATIVOS    = f"{_G['jur']}.contratos_ativos"
    CERTIDOES           = f"{_G['jur']}.certidoes"

# ═══════════════════════════════════════════════════════════════════════
# ENGENHARIA E P&D
# ═══════════════════════════════════════════════════════════════════════
class Engenharia:
    CATALOGO_ATIVO      = f"{_G['eng']}.catalogo_ativo"
    BOM_COMPLETO        = f"{_G['eng']}.bom_completo"
    PIPELINE_PRODUTOS   = f"{_G['eng']}.pipeline_produtos"
