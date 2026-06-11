-- ═══════════════════════════════════════════════════════════════════════════
-- SILVER_FINANCEIRO — Camada Prata Financeira (Vanguardia / Teste)
-- Projeto: vanguardia-prod-466114
-- Dataset: silver_financeiro
-- Base para DRE Nevoni — Regime de Caixa e Competência
--
-- Fontes:
--   dm_payments.{fact_payable, fact_receivable, fact_settled_title, dim_financial_item}
--   dm_orders.{fact_sales_order, fact_order_item, dim_operation_nature}
--   dm_partners.dim_partner
--   dm_products.dim_item
--
-- Histórico de correções:
--   05.02/05.05 → MOVIMENTACAO INTRAGRUPO | 22.40 → FORA DO P&L
--   confirmado Diego 12/05/2026
--   competência REALIZADO: corrigido para usar document_amount (não paid_amount)
--   20/05/2026
-- ═══════════════════════════════════════════════════════════════════════════

-- NOTA: param_fin_plano_contas NÃO é reconstruída aqui.
-- A tabela com os 394 itens e mapeamentos DE-PARA (subgroup/group_name/account_sign)
-- é gerenciada manualmente via script separado (setup_param_financeiro.py).
-- Isso evita sobrescrever os mapeamentos aprovados por Diego.


-- ═══════════════════════════════════════════════════════════════════════════
-- TABELA 2 — FATURAMENTO RATEADO POR ITEM
-- Regra: pedidos faturados (invoice_number IS NOT NULL), direção Saída (S),
-- natureza financeiro/fiscal (financial_flag = 'F'), sem devoluções (is_return = 'N').
-- Rateio por item: cada item recebe % proporcional ao seu valor no pedido.
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `vanguardia-prod-466114.silver_financeiro.slv_fin_faturamento_rateado`
PARTITION BY DATE_TRUNC(order_date, MONTH)
CLUSTER BY partner_code, item_code
AS
WITH naturezas_faturamento AS (
  SELECT DISTINCT nature_code
  FROM `vanguardia-prod-466114.dm_orders.dim_operation_nature`
  WHERE direction = 'S'
    AND financial_flag = 'F'
    AND (is_return IS NULL OR is_return = 'N' OR is_return = '')
),

-- Pedidos de venda faturados
pedidos_faturados AS (
  SELECT
    so.order_number,
    so.invoice_number,
    so.partner_code,
    so.company_code,
    so.nature_code,
    so.salesperson_code,
    so.order_date,
    so.invoice_date,
    so.payment_cond_code,
    so.product_amount,
    so.freight_amount,
    so.ipi_amount,
    so.icms_amount,
    so.total_amount
  FROM `vanguardia-prod-466114.dm_orders.fact_sales_order` so
  INNER JOIN naturezas_faturamento nf ON so.nature_code = nf.nature_code
  WHERE so.invoice_number IS NOT NULL
    AND so.excluded_at IS NULL                           -- regra silver: descarta notas canceladas (YDATEXC)
),

-- Itens do pedido com valor de linha
itens AS (
  SELECT
    oi.order_number,
    oi.item_code,
    oi.quantity,
    oi.unit_price                                                           AS line_value,
    SUM(oi.unit_price) OVER (PARTITION BY oi.order_number)                  AS order_items_total
  FROM `vanguardia-prod-466114.dm_orders.fact_order_item` oi
  WHERE oi.operation_type = 'S'
    AND oi.excluded_at IS NULL                           -- regra silver: descarta itens de notas canceladas
),

-- Rateio: cada item recebe % do total do pedido
rateado AS (
  SELECT
    pf.order_number,
    pf.invoice_number,
    pf.partner_code,
    pf.company_code,
    pf.nature_code,
    pf.salesperson_code,
    pf.order_date,
    pf.invoice_date,
    pf.payment_cond_code,
    it.item_code,
    it.quantity,
    it.line_value,
    it.order_items_total,
    SAFE_DIVIDE(it.line_value, it.order_items_total)                        AS item_pct,
    -- Rateio de encargos do pedido proporcionalmente ao item
    ROUND(pf.freight_amount * SAFE_DIVIDE(it.line_value, it.order_items_total), 4) AS freight_allocated,
    ROUND(pf.ipi_amount    * SAFE_DIVIDE(it.line_value, it.order_items_total), 4) AS ipi_allocated,
    ROUND(pf.icms_amount   * SAFE_DIVIDE(it.line_value, it.order_items_total), 4) AS icms_allocated,
    -- Total do item incluindo rateios
    ROUND(
      it.line_value
      + pf.freight_amount * SAFE_DIVIDE(it.line_value, it.order_items_total)
      + pf.ipi_amount     * SAFE_DIVIDE(it.line_value, it.order_items_total),
      4
    )                                                                       AS total_item_allocated
  FROM pedidos_faturados pf
  INNER JOIN itens it ON pf.order_number = it.order_number
)

SELECT
  r.*,
  di.item_name,
  di.group_code,
  di.family_code,
  di.material_code,
  dp.partner_name,
  CURRENT_TIMESTAMP() AS etl_loaded_at
FROM rateado r
LEFT JOIN `vanguardia-prod-466114.dm_products.dim_item`    di ON r.item_code    = di.item_code
LEFT JOIN `vanguardia-prod-466114.dm_partners.dim_partner` dp ON r.partner_code = dp.partner_code;


-- ═══════════════════════════════════════════════════════════════════════════
-- TABELA 3 — TÍTULOS LIQUIDADOS (PAGAS E RECEBIDAS)
-- Regime de Caixa: data de referência = payment_date
-- settlement_type: 'D' = receita (a receber → recebida), 'E' = despesa (a pagar → paga)
-- Rateio financeiro: múltiplos títulos do mesmo pedido → pct proporcional ao total
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `vanguardia-prod-466114.silver_financeiro.slv_fin_titulo_realizado`
PARTITION BY DATE_TRUNC(payment_date, MONTH)
CLUSTER BY company_code, financial_item_code
AS
WITH titulos AS (
  SELECT
    st.title_number,
    st.order_number,
    st.settlement_type,
    st.partner_code,
    st.company_code,
    st.bank_code,
    st.issue_date,
    st.due_date,
    st.payment_date,
    st.document_amount,
    st.paid_amount,
    st.financial_item_code,
    -- Rateio financeiro: cada título é % do total do mesmo pedido
    SAFE_DIVIDE(
      st.document_amount,
      SUM(st.document_amount) OVER (PARTITION BY st.order_number)
    )                                                                       AS installment_pct
  FROM `vanguardia-prod-466114.dm_payments.fact_settled_title` st
  WHERE st.payment_date IS NOT NULL
    AND st.excluded_at IS NULL                           -- regra silver: descarta títulos cancelados
)

SELECT
  t.*,
  pc.subgroup,
  pc.group_name,
  pc.account_sign,
  dp.partner_name,
  CURRENT_TIMESTAMP() AS etl_loaded_at
FROM titulos t
LEFT JOIN `vanguardia-prod-466114.silver_financeiro.param_fin_plano_contas` pc
       ON t.financial_item_code = pc.financial_item_code
LEFT JOIN `vanguardia-prod-466114.dm_partners.dim_partner` dp
       ON t.partner_code = dp.partner_code;


-- ═══════════════════════════════════════════════════════════════════════════
-- TABELA 4 — TÍTULOS A LIQUIDAR (PAGAR E RECEBER — em aberto)
-- Inclui: contas a pagar (YENCDES='E') e a receber (YENCDES='D')
-- settlement_type: 'D' = a receber, 'E' = a pagar
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `vanguardia-prod-466114.silver_financeiro.slv_fin_titulo_realizar`
PARTITION BY DATE_TRUNC(due_date, MONTH)
CLUSTER BY company_code, financial_item_code
AS
WITH contas_pagar AS (
  SELECT
    ap.title_number,
    ap.order_number,
    'E'                                                                     AS settlement_type,
    ap.partner_code,
    ap.company_code,
    ap.bank_code,
    ap.department_code,
    ap.issue_date,
    ap.due_date,
    NULL                                                                    AS payment_date,
    ap.document_amount,
    ap.net_amount,
    ap.financial_item_code,
    SAFE_DIVIDE(
      ap.document_amount,
      SUM(ap.document_amount) OVER (PARTITION BY ap.order_number)
    )                                                                       AS installment_pct
  FROM `vanguardia-prod-466114.dm_payments.fact_payable` ap
  WHERE ap.excluded_at IS NULL                           -- regra silver: descarta títulos cancelados
),

contas_receber AS (
  SELECT
    ar.title_number,
    ar.order_number,
    'D'                                                                     AS settlement_type,
    ar.partner_code,
    ar.company_code,
    NULL                                                                    AS bank_code,
    NULL                                                                    AS department_code,
    ar.issue_date,
    ar.due_date,
    NULL                                                                    AS payment_date,
    ar.document_amount,
    ar.net_amount,
    ar.financial_item_code,
    SAFE_DIVIDE(
      ar.document_amount,
      SUM(ar.document_amount) OVER (PARTITION BY ar.order_number)
    )                                                                       AS installment_pct
  FROM `vanguardia-prod-466114.dm_payments.fact_receivable` ar
  WHERE ar.excluded_at IS NULL                           -- regra silver: descarta títulos cancelados
),

union_titulos AS (
  SELECT * FROM contas_pagar
  UNION ALL
  SELECT * FROM contas_receber
)

SELECT
  ut.*,
  pc.subgroup,
  pc.group_name,
  pc.account_sign,
  dp.partner_name,
  CURRENT_TIMESTAMP() AS etl_loaded_at
FROM union_titulos ut
LEFT JOIN `vanguardia-prod-466114.silver_financeiro.param_fin_plano_contas` pc
       ON ut.financial_item_code = pc.financial_item_code
LEFT JOIN `vanguardia-prod-466114.dm_partners.dim_partner` dp
       ON ut.partner_code = dp.partner_code;


-- ═══════════════════════════════════════════════════════════════════════════
-- TABELA 5 — DRE REGIME DE CAIXA
-- Realizado:  data = payment_date (quando entrou/saiu o caixa)
-- A Realizar: data = due_date (previsão de entrada/saída)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `vanguardia-prod-466114.silver_financeiro.slv_fin_dre_caixa`
PARTITION BY DATE_TRUNC(dre_date, MONTH)
CLUSTER BY group_name, company_code
AS
-- Realizado (liquidados — usa payment_date)
SELECT
  'REALIZADO'                                                               AS status,
  'CAIXA'                                                                   AS regime,
  payment_date                                                              AS dre_date,
  title_number,
  order_number,
  settlement_type,
  partner_code,
  partner_name,
  company_code,
  financial_item_code,
  subgroup,
  group_name,
  account_sign,
  installment_pct,
  document_amount,
  paid_amount                                                               AS effective_amount,
  NULL                                                                      AS net_amount
FROM `vanguardia-prod-466114.silver_financeiro.slv_fin_titulo_realizado`

UNION ALL

-- A realizar (em aberto — usa due_date)
SELECT
  'REALIZAR'                                                                AS status,
  'CAIXA'                                                                   AS regime,
  due_date                                                                  AS dre_date,
  title_number,
  order_number,
  settlement_type,
  partner_code,
  partner_name,
  company_code,
  financial_item_code,
  subgroup,
  group_name,
  account_sign,
  installment_pct,
  document_amount,
  NULL                                                                      AS effective_amount,
  net_amount
FROM `vanguardia-prod-466114.silver_financeiro.slv_fin_titulo_realizar`;


-- ═══════════════════════════════════════════════════════════════════════════
-- TABELA 6 — DRE REGIME DE COMPETÊNCIA
-- Realizado:  data = issue_date (competência = data de emissão)
--             valor = document_amount (valor do documento, não o pago)
-- A Realizar: data = issue_date (idem)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `vanguardia-prod-466114.silver_financeiro.slv_fin_dre_competencia`
PARTITION BY DATE_TRUNC(dre_date, MONTH)
CLUSTER BY group_name, company_code
AS
SELECT
  'REALIZADO'                                                               AS status,
  'COMPETENCIA'                                                             AS regime,
  issue_date                                                                AS dre_date,
  title_number,
  order_number,
  settlement_type,
  partner_code,
  partner_name,
  company_code,
  financial_item_code,
  subgroup,
  group_name,
  account_sign,
  installment_pct,
  document_amount,
  document_amount                                                           AS effective_amount,
  NULL                                                                      AS net_amount
FROM `vanguardia-prod-466114.silver_financeiro.slv_fin_titulo_realizado`

UNION ALL

SELECT
  'REALIZAR'                                                                AS status,
  'COMPETENCIA'                                                             AS regime,
  issue_date                                                                AS dre_date,
  title_number,
  order_number,
  settlement_type,
  partner_code,
  partner_name,
  company_code,
  financial_item_code,
  subgroup,
  group_name,
  account_sign,
  installment_pct,
  document_amount,
  NULL                                                                      AS effective_amount,
  net_amount
FROM `vanguardia-prod-466114.silver_financeiro.slv_fin_titulo_realizar`;


-- ═══════════════════════════════════════════════════════════════════════════
-- TABELA 7 — RESUMO MENSAL (AGG)
-- Sumariza DRE caixa + competência por year_month × grupo × regime × empresa.
-- Coluna `amount`: soma de effective_amount (realizado) ou document_amount (realizar).
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `vanguardia-prod-466114.silver_financeiro.slv_fin_resumo_mensal`
CLUSTER BY regime, group_name, company_code
AS
WITH caixa AS (
  SELECT
    regime,
    FORMAT_DATE('%Y-%m', dre_date)                                          AS year_month,
    status,
    company_code,
    settlement_type,
    group_name,
    subgroup,
    account_sign,
    SUM(COALESCE(effective_amount, document_amount))                        AS amount,
    COUNT(*)                                                                AS title_count
  FROM `vanguardia-prod-466114.silver_financeiro.slv_fin_dre_caixa`
  WHERE dre_date IS NOT NULL
  GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
),

competencia AS (
  SELECT
    regime,
    FORMAT_DATE('%Y-%m', dre_date)                                          AS year_month,
    status,
    company_code,
    settlement_type,
    group_name,
    subgroup,
    account_sign,
    SUM(COALESCE(effective_amount, document_amount))                        AS amount,
    COUNT(*)                                                                AS title_count
  FROM `vanguardia-prod-466114.silver_financeiro.slv_fin_dre_competencia`
  WHERE dre_date IS NOT NULL
  GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
)

SELECT *, CURRENT_TIMESTAMP() AS etl_loaded_at FROM caixa
UNION ALL
SELECT *, CURRENT_TIMESTAMP() AS etl_loaded_at FROM competencia;


-- ═══════════════════════════════════════════════════════════════════════════
-- TABELA 8 — MARGEM PRODUTO (baixa prioridade — construir após validação)
-- Cruza faturamento rateado com custo médio do item.
-- DEPENDÊNCIA: fact_item_cost (não disponível ainda no ERP).
-- Por ora: usa apenas faturamento (sem dedução de custo).
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE TABLE `vanguardia-prod-466114.silver_financeiro.slv_fin_margem_produto`
CLUSTER BY item_code, company_code
AS
SELECT
  fr.item_code,
  fr.item_name,
  fr.group_code,
  fr.family_code,
  fr.material_code,
  fr.company_code,
  FORMAT_DATE('%Y-%m', fr.order_date)                                       AS year_month,
  SUM(fr.line_value)                                                        AS revenue_item,
  SUM(fr.freight_allocated)                                                 AS freight_total,
  SUM(fr.ipi_allocated)                                                     AS ipi_total,
  SUM(fr.total_item_allocated)                                              AS revenue_total,
  NULL                                                                      AS cost_total,    -- aguarda fact_item_cost
  NULL                                                                      AS gross_margin,  -- aguarda fact_item_cost
  COUNT(DISTINCT fr.order_number)                                           AS order_count,
  SUM(fr.quantity)                                                          AS total_qty,
  CURRENT_TIMESTAMP()                                                       AS etl_loaded_at
FROM `vanguardia-prod-466114.silver_financeiro.slv_fin_faturamento_rateado` fr
GROUP BY 1, 2, 3, 4, 5, 6, 7;
