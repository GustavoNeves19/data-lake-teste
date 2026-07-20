-- =============================================================================
-- build_gold_price.sql
-- Gold layer — Painel PRICE (lucro líquido / margem por produto × canal)
-- Projeto: sapient-metrics-492914-m7 (Nevoni/prod) · Dataset: gold_price
--
-- Nasce da reunião 07/07/2026 (pedido Vini/Maurício): margem R$ e % por item e
-- canal de venda, com simulação. Estratégia aprovada pelo grupo (Fred): extrair
-- do BQ o que já existe e deixar o resto EDITÁVEL na tela (param_price_custos,
-- gravada pelo app). Ver docs/PAINEL_PRICE.md.
--
-- ⚠️ O que a lake ENTREGA hoje nesta branch vs o que é MANUAL:
--   ✅ faturamento, quantidade, ICMS, IPI (da nota), canal (YCODVEN)
--   ✅ custo da peça       → dim_item.linked_items_cost (ITENS.YVALITMVIN, custo de
--                            explosão/somatória das peças no cadastro do item).
--                            Decisão da reunião 14/07/2026: não usar YVALCUS como
--                            custo principal do PRICE; YVALCUS fica só para auditoria.
--   ❌ tarifa ML direta    → sem conector Mercado Livre na lake
--   ❌ Ads/comissão/IRPJ-CSLL/crédito ICMS-IPI/frete → param manual (app)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. param_price_custos  — camada MANUAL, editável pelo app (4 admins)
--    Grão: item_code × canal × mes (1º dia do mês).
--    CREATE IF NOT EXISTS aqui garante schema estável mesmo antes do 1º save.
--    O app (api/price.py) usa DDL IDÊNTICO neste mesmo objeto. Percentuais são
--    sobre o faturamento (0–100). custo_peca é R$ por unidade.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sapient-metrics-492914-m7.gold_price.param_price_custos` (
  item_code             STRING  NOT NULL,
  canal                 STRING  NOT NULL,
  mes                   DATE    NOT NULL,
  custo_peca            FLOAT64,   -- R$/unidade (override/simulação sobre o custo ERP)
  pct_ads               FLOAT64,   -- % faturamento (Ads/marketing marketplace)
  pct_comissao          FLOAT64,   -- % faturamento (comissão vendedor interno OU marketplace)
  pct_irpj_csll         FLOAT64,   -- legado: % faturamento (IRPJ/CSLL agrupado)
  pct_irpj              FLOAT64,   -- % faturamento (IRPJ)
  pct_csll              FLOAT64,   -- % faturamento (CSLL)
  pct_pis               FLOAT64,   -- % faturamento (PIS)
  pct_cofins            FLOAT64,   -- % faturamento (COFINS)
  pct_credito_icms_ipi  FLOAT64,   -- legado: % faturamento (crédito ICMS/IPI agrupado)
  pct_credito_icms      FLOAT64,   -- % faturamento (crédito ICMS)
  pct_credito_ipi       FLOAT64,   -- % faturamento (crédito IPI)
  mao_obra_unit         FLOAT64,   -- R$/unidade (mão de obra de produção)
  pct_custo_fixo        FLOAT64,   -- % faturamento (rateio de custo fixo)
  pct_outras            FLOAT64,   -- % faturamento (frete e outras despesas diretas)
  updated_by            STRING,
  updated_at            TIMESTAMP
);

ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS pct_irpj FLOAT64;
ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS pct_csll FLOAT64;
ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS pct_pis FLOAT64;
ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS pct_cofins FLOAT64;
ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS pct_credito_icms FLOAT64;
ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS pct_credito_ipi FLOAT64;
ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS mao_obra_unit FLOAT64;
ALTER TABLE `sapient-metrics-492914-m7.gold_price.param_price_custos`
ADD COLUMN IF NOT EXISTS pct_custo_fixo FLOAT64;


-- -----------------------------------------------------------------------------
-- 2. gold_price_margem  — camada FATOS (100% ERP/BQ)
--    Grão: item_code × canal × mes. Janela: últimos 13 meses por invoice_date.
--    Filtro de faturamento CANÔNICO (idêntico a silver_com_vendas / api.queries):
--      financial_flag<>'N' · channel_code<>'000054' · invoice_date preenchido.
--    ⚠️ BUG corrigido 15/07/2026: a versão anterior tinha um filtro extra
--    `order_status IN (3,4)` que NENHUMA outra query do sistema usa. Pedidos de
--    Marketplace (Mercado Livre em especial) vêm com order_status NULL/0, então
--    esse filtro escondia ~99% do faturamento do canal Mercado Livre (R$4,8k
--    exibidos vs R$3,52M reais nos últimos 13 meses — achado ao investigar por
--    que o item 5005BR-MELI sumia do PRICE). Removido para bater com a régua
--    canônica do resto do Comercial/RFV.
--    Canal derivado de channel_code (YCODVEN) — o grão fino separa Meli/Amazon/
--    Shopee do balde "Distribuidor/Interno" (o CANAL_CASE por YGRUVEN usado no
--    resto do Comercial NÃO distingue Meli de Amazon, aqui precisamos por canal
--    de venda). fact_order_item não carrega canal → JOIN no cabeçalho.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.gold_price.gold_price_margem`
CLUSTER BY canal, item_code AS
WITH itens AS (
  SELECT
    it.item_code,
    DATE_TRUNC(o.invoice_date, MONTH) AS mes,
    CASE
      WHEN o.channel_code = '92'                         THEN 'Mercado Livre'
      WHEN o.channel_code = 'AM'                         THEN 'Amazon'
      WHEN o.channel_code IN ('SH','SHOPEE')             THEN 'Shopee'
      WHEN o.channel_code IN ('LI','OL','90','91','AME') THEN 'Outros Marketplaces'
      ELSE 'Distribuidor/Interno'
    END AS canal,
    it.order_number,
    o.partner_code,
    it.quantity,
    it.unit_price,
    it.icms_amount,
    it.ipi_amount
  FROM `sapient-metrics-492914-m7.dm_orders.fact_order_item` it
  JOIN `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
    ON o.order_number = it.order_number
  JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
    ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
  WHERE
    -- ⚠️ DECISÃO PENDENTE (07/07): exclui SITE-LOJA (000054, ~R$520k/13m de
    -- e-commerce) por herança da metodologia comercial/RFV. Para o PRICE de
    -- marketplace talvez deva ENTRAR — confirmar com o time. Ver docs.
    o.channel_code <> '000054'
    AND o.invoice_date IS NOT NULL
    AND o.invoice_date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH)
    AND o.invoice_date <= CURRENT_DATE()
)
SELECT
  i.item_code,
  COALESCE(di.item_name, i.item_code)  AS item_name,
  i.canal,
  i.mes,
  COUNT(DISTINCT i.order_number)       AS n_pedidos,
  SUM(i.quantity)                      AS quantidade,
  -- ✅ VALIDADO 08/07: unit_price é UNITÁRIO. SUM(unit_price*quantity) bate ao
  -- centavo com product_amount (YVALPRO) do cabeçalho (Jun/2026: R$ 691.173,07
  -- item vs R$ 691.173,06 header). Faturamento reconcilia com a metodologia oficial.
  SUM(i.unit_price * i.quantity)       AS faturamento,
  SAFE_DIVIDE(SUM(i.unit_price * i.quantity), SUM(i.quantity)) AS ticket_medio,
  SUM(i.icms_amount)                   AS imposto_icms,
  SUM(i.ipi_amount)                    AS imposto_ipi,
  -- custo da peça: decisão 14/07/2026: usar custo de explosão do cadastro
  -- (ITENS.YVALITMVIN).
  NULLIF(MAX(di.linked_items_cost), 0)  AS custo_peca_erp,
  CURRENT_TIMESTAMP()                  AS etl_loaded_at
FROM itens i
LEFT JOIN `sapient-metrics-492914-m7.dm_products.dim_item` di
  ON di.item_code = i.item_code
GROUP BY i.item_code, item_name, i.canal, i.mes;


-- -----------------------------------------------------------------------------
-- 3. gold_price_margem_uf — detalhe por estado para explicar impacto do ICMS
--    Grão: item_code × canal × mes × UF. Mesma base da tabela principal.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.gold_price.gold_price_margem_uf`
CLUSTER BY canal, item_code, uf AS
WITH itens AS (
  SELECT
    it.item_code,
    DATE_TRUNC(o.invoice_date, MONTH) AS mes,
    CASE
      WHEN o.channel_code = '92'                         THEN 'Mercado Livre'
      WHEN o.channel_code = 'AM'                         THEN 'Amazon'
      WHEN o.channel_code IN ('SH','SHOPEE')             THEN 'Shopee'
      WHEN o.channel_code IN ('LI','OL','90','91','AME') THEN 'Outros Marketplaces'
      ELSE 'Distribuidor/Interno'
    END AS canal,
    COALESCE(NULLIF(UPPER(TRIM(p.state)), ''), 'UF nao informada') AS uf,
    it.order_number,
    it.quantity,
    it.unit_price,
    it.icms_amount,
    it.ipi_amount
  FROM `sapient-metrics-492914-m7.dm_orders.fact_order_item` it
  JOIN `sapient-metrics-492914-m7.dm_orders.fact_sales_order` o
    ON o.order_number = it.order_number
  JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
    ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
  LEFT JOIN `sapient-metrics-492914-m7.dm_partners.dim_partner` p
    ON CAST(p.partner_code AS STRING) = CAST(o.partner_code AS STRING)
  WHERE
    -- filtro canônico: ver comentário no CREATE TABLE gold_price_margem acima
    -- (bug do order_status IN (3,4) corrigido 15/07/2026, mesma correção aqui).
    o.channel_code <> '000054'
    AND o.invoice_date IS NOT NULL
    AND o.invoice_date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH)
    AND o.invoice_date <= CURRENT_DATE()
)
SELECT
  i.item_code,
  COALESCE(di.item_name, i.item_code)  AS item_name,
  i.canal,
  i.mes,
  i.uf,
  COUNT(DISTINCT i.order_number)       AS n_pedidos,
  SUM(i.quantity)                      AS quantidade,
  SUM(i.unit_price * i.quantity)       AS faturamento,
  SAFE_DIVIDE(SUM(i.unit_price * i.quantity), SUM(i.quantity)) AS ticket_medio,
  SUM(i.icms_amount)                   AS imposto_icms,
  SUM(i.ipi_amount)                    AS imposto_ipi,
  NULLIF(MAX(di.linked_items_cost), 0)  AS custo_peca_erp,
  CURRENT_TIMESTAMP()                  AS etl_loaded_at
FROM itens i
LEFT JOIN `sapient-metrics-492914-m7.dm_products.dim_item` di
  ON di.item_code = i.item_code
GROUP BY i.item_code, item_name, i.canal, i.mes, i.uf;
