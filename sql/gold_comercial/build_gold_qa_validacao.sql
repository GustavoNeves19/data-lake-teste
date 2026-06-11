-- =============================================================================
-- gold_qa_validacao — Cascata de validação em 4 camadas
-- Camadas: Nevoni (gestor) → ERP (NSR_ERP) → BQ (silver/gold) → Dashboard
-- Cada Δ é registrado pra auditoria
-- =============================================================================
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.gold_comercial.gold_qa_validacao` (
    -- Chave
    data_referencia      DATE        NOT NULL,
    escopo               STRING      NOT NULL,   -- GERAL | HOSPITALAR | FARMACIAS | SAC | <vendedor>
    metrica              STRING      NOT NULL,   -- faturamento | clientes | notas

    -- Camada 1 — Nevoni (declaração do gestor)
    valor_nevoni         NUMERIC,
    fonte_nevoni         STRING,                 -- "planilha Alves RFV Mai/2026 02/06/2026"

    -- Camada 2 — ERP NSR_ERP (fonte da verdade)
    valor_erp            NUMERIC,
    query_erp_ref        STRING,                 -- nome do arquivo SQL canônico
    delta_erp_nevoni     NUMERIC,                -- erp - nevoni
    pct_erp_nevoni       NUMERIC,

    -- Camada 3 — BQ silver/gold
    valor_bq             NUMERIC,
    tabela_bq_ref        STRING,                 -- ex: "silver_com_rfv_base@2026-05-31"
    delta_bq_erp         NUMERIC,                -- bq - erp (deve ser ~0)
    pct_bq_erp           NUMERIC,

    -- Camada 4 — calculada em runtime no dash (sempre = valor_bq)
    -- não tem coluna; o dashboard valida no momento de renderizar

    -- Status agregado
    status               STRING      NOT NULL,   -- VERDE <1% | AMARELO 1-3% | VERMELHO >3%
    delta_total_pct      NUMERIC,                -- (bq - nevoni) / nevoni

    -- Metadados
    validado_em          TIMESTAMP   NOT NULL,
    observacao           STRING                  -- ex: "regra: sem YDATEXC, sem SITE-LOJA"
)
PARTITION BY data_referencia
CLUSTER BY escopo, metrica;
