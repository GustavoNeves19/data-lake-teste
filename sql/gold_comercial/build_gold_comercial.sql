-- =============================================================================
-- build_gold_comercial.sql
-- Gold layer — Setor Comercial / Inteligência de Vendas
-- Projeto: sapient-metrics-492914-m7 (Nevoni/prod)
-- Fontes:  silver_comercial, crm_raw (Pipedrive), goto_raw, dm_orders
--
-- Tabelas:
--   1. gold_com_cliente_360       — visão por cliente: RFV + CRM + alertas
--   2. gold_com_alerta_comercial  — alertas acionáveis para o time de vendas
--   3. gold_com_vendedor_painel   — KPIs por vendedor: ERP + CRM + GoTo
--   4. gold_com_pipeline_crm      — saúde do funil Pipedrive por pipeline/estágio
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. gold_com_cliente_360
--    Grain: 1 linha por partner_code (cliente ERP da carteira ativa)
--
--    Responde:
--      - Qual o segmento RFV atual do cliente?
--      - Ele está sendo trabalhado no CRM? Tem deal aberto?
--      - Qual o valor em pipeline? Quando foi o último contato?
--      - Flags de inteligência: oportunidade perdida, churn silencioso, etc.
--
--    NOTA: usa a melhor ligação da entity_bridge (cnpj_exact > name_fuzzy,
--    maior score). Clientes sem match ficam com org_id NULL mas aparecem na tabela.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360` AS
WITH

-- Melhor org_id por partner_code (cnpj_exact tem prioridade)
best_bridge AS (
    SELECT
        partner_code,
        partner_name,
        org_id,
        org_name,
        match_type,
        match_score,
        ROW_NUMBER() OVER (
            PARTITION BY partner_code
            ORDER BY
                CASE match_type WHEN 'cnpj_exact' THEN 1 WHEN 'name_fuzzy' THEN 2 ELSE 3 END,
                match_score DESC
        ) AS rn
    FROM `sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge`
    WHERE match_type != 'unmatched'
),

-- Todos os deals de todos os pipelines comerciais (exceto SAC)
deals_all AS (
    SELECT org_id, deal_id, status, value, add_time, won_time,
           expected_close_date, pipeline_id, owner_id
    FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_distribuidores`
    WHERE NOT COALESCE(is_deleted, FALSE)
    UNION ALL
    SELECT org_id, deal_id, status, value, add_time, won_time,
           expected_close_date, pipeline_id, owner_id
    FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_farmacia`
    WHERE NOT COALESCE(is_deleted, FALSE)
    UNION ALL
    SELECT org_id, deal_id, status, value, add_time, won_time,
           expected_close_date, pipeline_id, owner_id
    FROM `sapient-metrics-492914-m7.crm_raw.funil_vendas_farmacia`
    WHERE NOT COALESCE(is_deleted, FALSE)
),

-- Agrega métricas de deals por org_id
deal_metrics AS (
    SELECT
        org_id,
        COUNT(*)                                                    AS qtd_deals_total,
        COUNTIF(status = 'open')                                    AS qtd_deals_open,
        COUNTIF(status = 'won')                                     AS qtd_deals_won,
        COUNTIF(status = 'lost')                                    AS qtd_deals_lost,
        ROUND(SUM(CASE WHEN status = 'open' THEN value ELSE 0 END), 2)
                                                                    AS valor_pipeline_open,
        ROUND(SUM(CASE WHEN status = 'won'
                        AND won_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
                   THEN value ELSE 0 END), 2)                       AS valor_crm_won_12m,
        MAX(add_time)                                               AS ultimo_deal_criado_at,
        MAX(CASE WHEN status = 'open' THEN expected_close_date END) AS proximo_fechamento
    FROM deals_all
    GROUP BY org_id
)

SELECT
    -- Identificação ERP
    c.partner_code,
    c.partner_name,
    c.rfv_familia,
    c.salesperson_name                                              AS rfv_salesperson,

    -- Segmento RFV (CURRENT_DATE — dinâmico)
    COALESCE(r.classificacao_2, 'SEM RFV')                         AS segmento_rfv,
    COALESCE(r.classificacao_3, 99)                                AS segmento_num,
    r.freq_bucket,
    r.rec_bucket,
    r.frequencia,
    r.recencia_dias,
    ROUND(COALESCE(r.valor_total, 0), 2)                           AS faturamento_periodo,

    -- Ligação CRM (entity_bridge)
    b.org_id,
    b.org_name,
    b.match_type                                                   AS bridge_match_type,

    -- Métricas CRM
    COALESCE(dm.qtd_deals_total, 0)                                AS qtd_deals_total,
    COALESCE(dm.qtd_deals_open, 0)                                 AS qtd_deals_open,
    COALESCE(dm.qtd_deals_won, 0)                                  AS qtd_deals_won,
    ROUND(COALESCE(dm.valor_pipeline_open, 0), 2)                  AS valor_pipeline_open,
    ROUND(COALESCE(dm.valor_crm_won_12m, 0), 2)                    AS valor_crm_won_12m,
    dm.ultimo_deal_criado_at,
    dm.proximo_fechamento,
    DATE_DIFF(CURRENT_DATE(),
              DATE(dm.ultimo_deal_criado_at), DAY)                 AS dias_sem_deal_crm,

    -- ── Flags de Inteligência ──────────────────────────────────────────────────

    -- Campeões (1) + Fiéis (2) + Não pode perder (8) sem deal ativo no CRM
    -- → clientes de alto valor sem acompanhamento comercial registrado
    CASE
        WHEN COALESCE(r.classificacao_3, 99) IN (1, 2, 8)
         AND COALESCE(dm.qtd_deals_open, 0) = 0
        THEN TRUE ELSE FALSE
    END AS flag_oportunidade_sem_crm,

    -- Em risco (9) + Hibernando (10) sem deal aberto e sem contato recente
    -- → churn acontecendo em silêncio, ninguém está agindo
    CASE
        WHEN COALESCE(r.classificacao_3, 99) IN (9, 10)
         AND COALESCE(dm.qtd_deals_open, 0) = 0
         AND (dm.ultimo_deal_criado_at IS NULL
              OR DATE_DIFF(CURRENT_DATE(), DATE(dm.ultimo_deal_criado_at), DAY) > 60)
        THEN TRUE ELSE FALSE
    END AS flag_churn_silencioso,

    -- Em risco (9) + Hibernando (10) COM deal aberto → sinal positivo de recuperação
    CASE
        WHEN COALESCE(r.classificacao_3, 99) IN (9, 10)
         AND COALESCE(dm.qtd_deals_open, 0) > 0
        THEN TRUE ELSE FALSE
    END AS flag_recuperacao_em_andamento,

    -- Perdidos (11) com alto histórico de compra → candidato a reativação
    CASE
        WHEN COALESCE(r.classificacao_3, 99) = 11
         AND COALESCE(r.valor_total, 0) > 50000
        THEN TRUE ELSE FALSE
    END AS flag_reativacao_alto_valor,

    -- Cliente da carteira sem nenhum match no CRM → fora do radar digital
    CASE WHEN b.org_id IS NULL THEN TRUE ELSE FALSE END             AS flag_sem_crm,

    CURRENT_DATE()                                                  AS data_referencia

FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` c
-- IMPORTANTE: o silver_com_rfv_score guarda histórico mensal (1 snapshot/mês).
-- Sem filtrar o snapshot mais recente, o JOIN multiplica cada cliente pelo nº de
-- meses no histórico (quebra o grain "1 linha por partner_code" e infla os COUNTIF
-- dos alertas). Filtramos sempre a foto mais recente.
LEFT JOIN (
    SELECT *
    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
    WHERE DATE(data_referencia) = (
        SELECT MAX(DATE(data_referencia))
        FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
    )
) r
    ON  r.partner_name = c.partner_name
    AND r.rfv_familia  = c.rfv_familia
LEFT JOIN best_bridge b
    ON  b.partner_code = c.partner_code
    AND b.rn = 1
LEFT JOIN deal_metrics dm
    ON  dm.org_id = b.org_id
WHERE c.is_active = TRUE;


-- -----------------------------------------------------------------------------
-- 2. gold_com_alerta_comercial
--    Grain: 1 linha por partner_code × tipo de alerta
--    Responde: "O que precisa de ação AGORA?"
--
--    Tipos de alerta:
--      OPORTUNIDADE_SEM_CRM    — top cliente sem deal ativo
--      CHURN_SILENCIOSO        — em risco/adormecido sem contato
--      RECUPERACAO_ANDAMENTO   — em risco com deal aberto (bom sinal)
--      REATIVACAO_ALTO_VALOR   — cliente perdido com alto histórico
--      FORA_DO_RADAR_CRM       — carteira sem match no Pipedrive
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.gold_comercial.gold_com_alerta_comercial` AS
SELECT
    partner_code,
    partner_name,
    rfv_familia,
    rfv_salesperson,
    segmento_rfv,
    segmento_num,
    faturamento_periodo,
    org_id,
    org_name,
    qtd_deals_open,
    valor_pipeline_open,
    dias_sem_deal_crm,
    'OPORTUNIDADE_SEM_CRM'     AS tipo_alerta,
    'Cliente ' || segmento_rfv || ' sem deal ativo no Pipedrive. '
        || 'Faturamento ERP: R$ ' || CAST(ROUND(faturamento_periodo, 0) AS STRING)
        || ' — salesperson deveria estar trabalhando este cliente ativamente.'
                               AS descricao_alerta,
    1                          AS prioridade   -- mais urgente
FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360`
WHERE flag_oportunidade_sem_crm = TRUE

UNION ALL

SELECT
    partner_code, partner_name, rfv_familia, rfv_salesperson,
    segmento_rfv, segmento_num, faturamento_periodo,
    org_id, org_name, qtd_deals_open, valor_pipeline_open, dias_sem_deal_crm,
    'CHURN_SILENCIOSO',
    'Cliente ' || segmento_rfv || ' sem deal e sem contato CRM há '
        || CAST(COALESCE(dias_sem_deal_crm, 999) AS STRING) || ' dias. '
        || 'Faturamento acumulado: R$ ' || CAST(ROUND(faturamento_periodo, 0) AS STRING)
        || ' — risco de perda sem ação imediata.',
    2
FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360`
WHERE flag_churn_silencioso = TRUE

UNION ALL

SELECT
    partner_code, partner_name, rfv_familia, rfv_salesperson,
    segmento_rfv, segmento_num, faturamento_periodo,
    org_id, org_name, qtd_deals_open, valor_pipeline_open, dias_sem_deal_crm,
    'RECUPERACAO_ANDAMENTO',
    'Cliente ' || segmento_rfv || ' em recuperação: '
        || CAST(qtd_deals_open AS STRING) || ' deal(s) aberto(s) | '
        || 'Pipeline: R$ ' || CAST(ROUND(valor_pipeline_open, 0) AS STRING) || '.',
    3
FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360`
WHERE flag_recuperacao_em_andamento = TRUE

UNION ALL

SELECT
    partner_code, partner_name, rfv_familia, rfv_salesperson,
    segmento_rfv, segmento_num, faturamento_periodo,
    org_id, org_name, qtd_deals_open, valor_pipeline_open, dias_sem_deal_crm,
    'REATIVACAO_ALTO_VALOR',
    'Cliente PERDIDO com faturamento histórico R$ '
        || CAST(ROUND(faturamento_periodo, 0) AS STRING)
        || ' — alto potencial de reativação.',
    4
FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360`
WHERE flag_reativacao_alto_valor = TRUE

UNION ALL

SELECT
    partner_code, partner_name, rfv_familia, rfv_salesperson,
    segmento_rfv, segmento_num, faturamento_periodo,
    NULL, NULL, 0, 0, NULL,
    'FORA_DO_RADAR_CRM',
    'Cliente ativo no ERP (R$ ' || CAST(ROUND(faturamento_periodo, 0) AS STRING)
        || ') sem correspondência no Pipedrive — invisível para o CRM.',
    5
FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360`
WHERE flag_sem_crm = TRUE
  AND COALESCE(faturamento_periodo, 0) > 0;


-- -----------------------------------------------------------------------------
-- 3. gold_com_vendedor_painel
--    Grain: 1 linha por rfv_salesperson (vendedor) — snapshot atual
--    Responde: "Qual é o portfólio e o desempenho de cada vendedor?"
--
--    Combina:
--      - Carteira RFV: distribuição de segmentos, faturamento ERP
--      - CRM: deals abertos, valor pipeline, won 12m
--      - GoTo: volume de ligações, duração média, sentimento IA
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.gold_comercial.gold_com_vendedor_painel` AS
WITH

-- Portfólio RFV por vendedor
portfolio AS (
    SELECT
        rfv_salesperson,
        rfv_familia,
        -- Grão "cliente por NOME" (regra Alves: filiais do mesmo nome = 1 cliente).
        -- cliente_360 é 1 linha por partner_code, então contamos DISTINCT partner_name
        -- para não inflar por filial. Mantém Clientes e alertas na mesma base.
        COUNT(DISTINCT partner_name)                                AS qtd_clientes_carteira,
        COUNT(DISTINCT IF(segmento_num = 1,        partner_name, NULL))  AS qtd_campeoes,
        COUNT(DISTINCT IF(segmento_num = 2,        partner_name, NULL))  AS qtd_fieis,
        COUNT(DISTINCT IF(segmento_num = 3,        partner_name, NULL))  AS qtd_fieis_potencial,
        COUNT(DISTINCT IF(segmento_num = 8,        partner_name, NULL))  AS qtd_nao_pode_perder,
        COUNT(DISTINCT IF(segmento_num IN (9, 10), partner_name, NULL))  AS qtd_em_risco_hibernando,
        COUNT(DISTINCT IF(segmento_num = 11,       partner_name, NULL))  AS qtd_perdidos,
        ROUND(SUM(COALESCE(faturamento_periodo, 0)), 2)             AS faturamento_erp_periodo,
        COUNT(DISTINCT IF(flag_oportunidade_sem_crm, partner_name, NULL)) AS alertas_oportunidade,
        COUNT(DISTINCT IF(flag_churn_silencioso,     partner_name, NULL)) AS alertas_churn,
        COUNT(DISTINCT IF(flag_sem_crm,              partner_name, NULL)) AS clientes_fora_radar
    FROM `sapient-metrics-492914-m7.gold_comercial.gold_com_cliente_360`
    GROUP BY rfv_salesperson, rfv_familia
),

-- Deals CRM por owner E POR FAMÍLIA — separa pipelines por domínio comercial
-- (Hospitalar/Distribuidores vs Farmácia vs SAC) pra evitar duplicar deals do
-- mesmo vendedor que atua em mais de uma família (ex: Kauã Rodrigues).
-- O match com rfv_salesperson é feito via param_com_vendedor_map (user_id = PK).
deals_por_vendedor AS (
    SELECT
        d.owner_id                                                  AS crm_user_id,
        d.familia_canal                                             AS rfv_familia,
        COUNT(*)                                                    AS qtd_deals_total,
        COUNTIF(d.status = 'open')                                  AS qtd_deals_open,
        COUNTIF(d.status = 'won')                                   AS qtd_deals_won,
        ROUND(SUM(CASE WHEN d.status = 'open' THEN d.value ELSE 0 END), 2)
                                                                    AS valor_pipeline_open,
        ROUND(SUM(CASE WHEN d.status = 'won'
                        AND d.won_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
                   THEN d.value ELSE 0 END), 2)                     AS valor_crm_won_12m
    FROM (
        -- HOSPITALAR (distribuidores hospitalares no Pipedrive)
        SELECT owner_id, status, value, won_time, 'HOSPITALAR' AS familia_canal
        FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_distribuidores` WHERE NOT COALESCE(is_deleted, FALSE)
        UNION ALL
        SELECT owner_id, status, value, won_time, 'HOSPITALAR' AS familia_canal
        FROM `sapient-metrics-492914-m7.crm_raw.funil_vendas_distribuidores` WHERE NOT COALESCE(is_deleted, FALSE)
        -- FARMÁCIAS
        UNION ALL
        SELECT owner_id, status, value, won_time, 'FARMACIAS' AS familia_canal
        FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_farmacia` WHERE NOT COALESCE(is_deleted, FALSE)
        UNION ALL
        SELECT owner_id, status, value, won_time, 'FARMACIAS' AS familia_canal
        FROM `sapient-metrics-492914-m7.crm_raw.funil_vendas_farmacia` WHERE NOT COALESCE(is_deleted, FALSE)
        -- SAC (3 pipelines próprios)
        UNION ALL
        SELECT owner_id, status, value, won_time, 'SAC' AS familia_canal
        FROM `sapient-metrics-492914-m7.crm_raw.sac_vendas` WHERE NOT COALESCE(is_deleted, FALSE)
        UNION ALL
        SELECT owner_id, status, value, won_time, 'SAC' AS familia_canal
        FROM `sapient-metrics-492914-m7.crm_raw.sac_atendimento` WHERE NOT COALESCE(is_deleted, FALSE)
    ) d
    GROUP BY d.owner_id, d.familia_canal
),

-- GoTo: ligações por usuário GoTo
-- goto_call_line.internal_user_key → goto_users.user_key
-- ai_sentiment já está na goto_call_line (não precisa join com goto_calls)
goto_por_usuario AS (
    SELECT
        gu.line_name                                               AS goto_user_name,
        COUNT(DISTINCT cl.conversation_space_id)                   AS qtd_ligacoes,
        ROUND(SUM(cl.duration_seconds) / 60.0, 1)                  AS duracao_total_min,
        ROUND(AVG(cl.duration_seconds) / 60.0, 1)                  AS duracao_media_min,
        COUNTIF(LOWER(cl.ai_sentiment) = 'positive')               AS ligacoes_positivas,
        COUNTIF(LOWER(cl.ai_sentiment) = 'negative')               AS ligacoes_negativas
    FROM `sapient-metrics-492914-m7.goto_raw.goto_call_line`   cl
    JOIN `sapient-metrics-492914-m7.goto_raw.goto_users`       gu
        ON gu.user_key = cl.internal_user_key
    GROUP BY gu.line_name
)

SELECT
    p.rfv_salesperson,
    p.rfv_familia,
    p.qtd_clientes_carteira,

    -- Distribuição RFV do portfólio
    p.qtd_campeoes,
    p.qtd_fieis,
    p.qtd_fieis_potencial,
    p.qtd_nao_pode_perder,
    p.qtd_em_risco_hibernando,
    p.qtd_perdidos,
    ROUND(SAFE_DIVIDE(p.qtd_campeoes + p.qtd_fieis, p.qtd_clientes_carteira) * 100, 1)
                                                                    AS pct_topo_carteira,

    -- Faturamento ERP
    p.faturamento_erp_periodo,
    ROUND(SAFE_DIVIDE(p.faturamento_erp_periodo, p.qtd_clientes_carteira), 2)
                                                                    AS ticket_medio_cliente,

    -- CRM
    COALESCE(dv.qtd_deals_open, 0)                                 AS crm_deals_open,
    COALESCE(dv.qtd_deals_won, 0)                                  AS crm_deals_won,
    COALESCE(dv.valor_pipeline_open, 0)                            AS crm_valor_pipeline,
    COALESCE(dv.valor_crm_won_12m, 0)                              AS crm_valor_won_12m,

    -- GoTo
    COALESCE(gv.qtd_ligacoes, 0)                                   AS goto_ligacoes,
    COALESCE(gv.duracao_total_min, 0)                              AS goto_duracao_total_min,
    COALESCE(gv.duracao_media_min, 0)                              AS goto_duracao_media_min,
    COALESCE(gv.ligacoes_positivas, 0)                             AS goto_ligacoes_positivas,
    ROUND(SAFE_DIVIDE(gv.ligacoes_positivas, gv.qtd_ligacoes) * 100, 1)
                                                                    AS goto_pct_sentimento_positivo,

    -- Alertas
    p.alertas_oportunidade,
    p.alertas_churn,
    p.clientes_fora_radar,

    CURRENT_DATE()                                                  AS data_referencia

FROM portfolio p
-- Usa user_id (PK imutável) para evitar falhas de nome com acentos/sobrenomes
LEFT JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_vendedor_map` vm
    ON vm.rfv_salesperson = p.rfv_salesperson
-- JOIN por user_id E família — evita duplicar deals quando o mesmo vendedor
-- atua em mais de uma carteira (Kauã atende Hospitalar E Farmácia).
LEFT JOIN deals_por_vendedor dv
    ON dv.crm_user_id = vm.crm_user_id
   AND dv.rfv_familia = p.rfv_familia
LEFT JOIN goto_por_usuario gv
    ON UPPER(gv.goto_user_name) = UPPER(p.rfv_salesperson)
ORDER BY p.rfv_familia, p.faturamento_erp_periodo DESC;


-- -----------------------------------------------------------------------------
-- 4. gold_com_pipeline_crm
--    Grain: pipeline_id × stage_id × status — snapshot atual do funil
--    Responde: "Onde estão os deals? Qual é o gargalo do funil?"
--
--    Inclui:
--      - Distribuição de deals por estágio
--      - Taxa de conversão e perda por estágio
--      - Valor médio por estágio
--      - Tempo médio no estágio (usando stage_change_time)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.gold_comercial.gold_com_pipeline_crm` AS
WITH deals_union AS (
    SELECT deal_id, pipeline_id, stage_id, status, value,
           add_time, won_time, lost_time, stage_change_time, lost_reason,
           expected_close_date
    FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_distribuidores`
    WHERE NOT COALESCE(is_deleted, FALSE)
    UNION ALL
    SELECT deal_id, pipeline_id, stage_id, status, value,
           add_time, won_time, lost_time, stage_change_time, lost_reason,
           expected_close_date
    FROM `sapient-metrics-492914-m7.crm_raw.recorrencia_farmacia`
    WHERE NOT COALESCE(is_deleted, FALSE)
    UNION ALL
    SELECT deal_id, pipeline_id, stage_id, status, value,
           add_time, won_time, lost_time, stage_change_time, lost_reason,
           expected_close_date
    FROM `sapient-metrics-492914-m7.crm_raw.funil_vendas_farmacia`
    WHERE NOT COALESCE(is_deleted, FALSE)
)
SELECT
    s.pipeline_id,
    s.pipeline_name,
    s.stage_id,
    s.stage_name,
    s.order_nr,
    d.status,

    COUNT(*)                                                        AS qtd_deals,
    ROUND(SUM(d.value), 2)                                         AS valor_total,
    ROUND(AVG(d.value), 2)                                         AS valor_medio,
    ROUND(AVG(
        DATE_DIFF(CURRENT_DATE(), DATE(d.stage_change_time), DAY)
    ), 1)                                                           AS dias_medio_no_estagio,

    -- Lost reason breakdown (top reason por estágio)
    APPROX_TOP_COUNT(d.lost_reason, 1)[OFFSET(0)].value           AS principal_motivo_perda,

    CURRENT_DATE()                                                  AS data_referencia

FROM deals_union d
JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_stage` s
    ON  s.stage_id    = d.stage_id
    AND s.pipeline_id = d.pipeline_id
GROUP BY
    s.pipeline_id, s.pipeline_name, s.stage_id, s.stage_name,
    s.order_nr, d.status
ORDER BY
    s.pipeline_id, s.order_nr, d.status;
