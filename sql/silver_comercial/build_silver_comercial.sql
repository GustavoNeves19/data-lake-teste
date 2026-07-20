-- =============================================================================
-- build_silver_comercial.sql
-- Silver layer — Setor Comercial / RFV + Entity Bridge
-- Projeto: sapient-metrics-492914-m7 (Nevoni/prod)
-- Fonte:   dm_orders, dm_partners, crm_raw (Pipedrive)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. param_com_rfv_carteira
--    Mapeamento cliente → família RFV → vendedor titular
--    Populado pelo script populate_carteira_v3.py
--    NOTA: partner_code é INT64 para fazer JOIN direto com fact_sales_order
--
--    Pós-reunião 27/05/2026: a carteira deixa de ser o filtro primário do RFV
--    (que agora vem do grupo do vendedor da venda — veja silver_com_vendas).
--    A carteira passa a ser usada apenas para enriquecer com o vendedor titular.
--    salesperson_group_code é o grupo do vendedor titular (FR/FA/PC).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` (
    partner_code           INT64     NOT NULL,
    partner_name           STRING,
    rfv_familia            STRING    NOT NULL,
    salesperson_name       STRING,
    salesperson_group_code STRING,                          -- FR | FA | PC (nullable p/ legacy)
    is_active              BOOL,
    created_at             TIMESTAMP,
    updated_at             TIMESTAMP
);


-- -----------------------------------------------------------------------------
-- 1b. param_com_grupo_familia
--    Mapeamento canônico grupo de vendedor (ERP YGRUVEN) → família RFV.
--    Confirmado por Frederico/DC-Info na reunião 27/05/2026:
--      FR (Farmácia) → FARMACIAS
--      FA (Farmer)   → HOSPITALAR
--      PC (Peças)    → HOSPITALAR (SAC aglutinado em Hospitalar, decisão 16/07/2026
--                       — reunião VanguardIA x Nevoni, confirmado com Natália/Alves)
--    Filtro RFV = grupos presentes nesta tabela.
--    Para incluir novo grupo (ex: e-commerce no futuro), adicionar linha aqui —
--    sem mexer no resto do silver.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.silver_comercial.param_com_grupo_familia` AS
SELECT 'FR' AS salesperson_group_code, 'FARMACIAS'  AS rfv_familia, 'Farmácia' AS group_name
UNION ALL SELECT 'FA', 'HOSPITALAR', 'Farmer'
UNION ALL SELECT 'PC', 'HOSPITALAR', 'Peças';


-- -----------------------------------------------------------------------------
-- 2. silver_com_vendas
--    Pedidos faturados dos últimos 13 meses, filtrados por grupo de vendedor.
--    NOTA: não usa dim_partner (tem apenas ~12% dos clientes do ERP);
--    o partner_name vem da própria carteira (populada via populate_carteira_v3.py)
--    e cai em fallback para o nome bruto do ERP quando o cliente ainda não
--    foi atribuído a uma carteira.
--
--    Filtros confirmados:
--      • financial_flag <> 'N' em dim_operation_nature — TODAS as operações que
--        geram financeiro, em qualquer momento. Per Frederico (DBA NSR, 27/03/2026):
--          N = não gera financeiro (excluir)
--          F = gera financeiro NA NOTA (faturamento)
--          P = gera financeiro NO PEDIDO
--          E = gera financeiro NA EXPEDIÇÃO
--        A versão anterior usava `= 'F'` e excluía R$ 1,33M de vendas legítimas
--        em códigos com flag P ou E (ex: 5101 11). Auditoria mai/2026 confirmou.
--
--      • salesperson_group_code IN ('FR','FA','PC') — decisão reunião 27/05/2026
--        com Frederico/DC-Info. O filtro anterior era por LISTA de vendedores
--        ativos da carteira, que IGNORAVA vendedores inativos no período
--        (Sequin, Cauã antigo, etc.) — gerando gap de R$ 1M+ vs planilha do Alves.
--        Frederico validou: filtro por grupo bate R$ 10.012.266 contra R$ 10.439k
--        da planilha geral do Alves (period abr/25-abr/26, Valpro). Famílias
--        vêm via JOIN com param_com_grupo_familia.
--
--      • salesperson_name NOT LIKE 'Eduardo%' / 'Karina%' — Eduardo Marques =
--        licitação (FA, mas fora do RFV Hospitalar). Karina Correia = vendedora
--        ATIVA do grupo FR mas atende DISTRIBUIDORES E REDES (não farmácia
--        ponta) — Alves confirmou em 28/05/2026: não entra na RFV.
--        LIKE em vez de IN porque o nome do ERP vem com sobrenome.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.silver_comercial.silver_com_vendas` AS
SELECT
    o.order_number,
    o.order_date,
    o.invoice_date,
    o.partner_code,
    COALESCE(c.partner_name, CAST(o.partner_code AS STRING))                 AS partner_name,
    gf.rfv_familia                                                            AS rfv_familia,
    -- rfv_salesperson: vendedor titular da carteira quando existir; senão, vendedor da venda.
    -- Mantém a noção de "dono do cliente" do Alves sem bloquear vendas de clientes não-carteirizados.
    COALESCE(c.salesperson_name, o.salesperson_name)                          AS rfv_salesperson,
    o.salesperson_code,
    o.salesperson_name                                                        AS sale_salesperson_name,
    o.salesperson_group_code,
    o.nature_code,
    o.company_code,
    o.product_amount,                                          -- yValPro: valor líquido (sem impostos/frete) — usado no RFV
    o.total_amount,                                            -- yValTot: valor total com impostos/frete — backup pra DRE
    o.order_status,
    EXTRACT(YEAR  FROM o.order_date) AS ano,
    EXTRACT(MONTH FROM o.order_date) AS mes
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`  o
JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_grupo_familia` gf
    ON  gf.salesperson_group_code = o.salesperson_group_code
JOIN `sapient-metrics-492914-m7.dm_orders.dim_operation_nature` n
    ON  n.nature_code     = o.nature_code
    AND n.financial_flag <> 'N'                           -- todas operações que geram financeiro (F=nota, P=pedido, E=expedição)
LEFT JOIN `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira` c
    ON  c.partner_code = o.partner_code
    AND c.rfv_familia  = gf.rfv_familia
    AND c.is_active    = TRUE
WHERE o.order_status IN (3, 4)
  -- excluded_at (YDATEXC) NÃO é filtrado — Alves congela planilha antes do
  -- cancelamento posterior; manter cancelados garante bater snapshot (decisão 02/06/2026).
  -- 28 notas canceladas no período Mai/25-Mai/26 = R$ 138k incluídas.
  AND o.channel_code <> '000054'                          -- exclui SITE-LOJA (canal mal cadastrado como FA/PC)
                                                          -- R$ 51.226 / 35 notas removidas. Decisão 02/06/2026.
  -- Filtros NOT LIKE 'EDUARDO%' e 'KARINA%' REMOVIDOS em 03/06/2026:
  -- decisão "ERP é fonte da verdade" — silver soma TODO o YGRUVEN FA/FR/PC,
  -- alinhado ao filtro canônico do Fred. Eduardo e Karina passam a entrar.
  AND o.invoice_date IS NOT NULL
  -- Janela dinâmica POR INVOICE_DATE (YDATNOT). Alinhado com o gabarito SQL
  -- do Frederico (DC-Info) entregue em 27/05/2026 — Alves usa "data emissão"
  -- da nota na planilha. Antes a janela era por order_date (YDATPED) e gerava
  -- gap contra a planilha em meses de virada (pedidos feitos no mês X mas
  -- faturados no mês X+1).
  -- Ex.: 20/05/2026 → invoice_date entre 01/05/2025 e 20/05/2026
  --      01/06/2026 → invoice_date entre 01/06/2025 e 01/06/2026
  AND o.invoice_date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH)
  AND o.invoice_date <= CURRENT_DATE();


-- -----------------------------------------------------------------------------
-- 3. silver_com_rfv_base
--    Agrega por nome de cliente × família (mesma lógica da planilha do Alves).
--    Grupos por partner_name para consolidar filiais com o mesmo nome ERP.
--    partner_codes_list contém todos os códigos ERP da entidade (para drill-down).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_base` AS
SELECT
    partner_name,
    rfv_familia,
    rfv_salesperson,
    STRING_AGG(DISTINCT CAST(partner_code AS STRING) ORDER BY CAST(partner_code AS STRING))
                                                                   AS partner_codes_list,
    MAX(order_date)                                                AS ultima_compra_data,
    -- Recência calculada a partir de CURRENT_DATE (janela dinâmica rolling)
    DATE_DIFF(CURRENT_DATE(), MAX(order_date), DAY)               AS recencia_dias,
    ROUND(DATE_DIFF(CURRENT_DATE(), MAX(order_date), DAY) / 30.0, 6) AS recencia_meses,
    COUNT(DISTINCT order_number)                                   AS frequencia,
    ROUND(SUM(product_amount), 2)                                  AS valor_total,        -- yValPro (valor líquido) — alinhado à planilha do Alves
    CURRENT_DATE()                                                 AS data_referencia
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_vendas`
GROUP BY
    partner_name,
    rfv_familia,
    rfv_salesperson;


-- -----------------------------------------------------------------------------
-- 4. silver_com_rfv_score
--    Aplica buckets F/R com thresholds por família e atribui segmento (1-11)
--
--    HOSPITALAR / SAC thresholds (confirmados Hugo Alves + planilha Giovanna — mai/2026):
--      F1 >= 5  | F2 = 4  | F3 = 3  | F4 = 2  | F5 = 1
--      SAC usa thresholds idênticos ao HOSPITALAR (confirmado planilha Giovanna, 79 clientes).
--      R1 <= 30d | R2 <= 60d | R3 <= 120d | R4 <= 180d | R5 > 180d
--      Ref. date da planilha original: 2026-04-02 (dashboard usa CURRENT_DATE())
--
--    FARMACIAS thresholds (confirmados planilha Ribeiro — mai/2026, 248 clientes):
--      F1 >= 7  | F2 = 5 ou 6 (>=5)  | F3 = 3 ou 4 (>=3)  | F4 = 2  | F5 = 1
--      R1 <= 30d | R2 <= 60d | R3 <= 120d | R4 <= 180d | R5 > 180d
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score` AS
WITH scored AS (
    SELECT
        b.*,

        -- Bucket Frequência
        --   HOSPITALAR/SAC (confirmado Hugo Alves — mai/2026):
        --     F1 >= 5 | F2 = 4 | F3 = 3 | F4 = 2 | F5 = 1
        --   FARMACIAS: F1 >= 7 | F2 = 5-6 | F3 = 3-4 | F4 = 2 | F5 = 1 (planilha Ribeiro)
        --   NOT LIKE '%FARMACIA%' pega Hosp/SAC e os NOVOS_* correspondentes (5+).
        CASE
            WHEN b.rfv_familia NOT LIKE '%FARMACIA%' THEN
                CASE
                    WHEN b.frequencia >= 5 THEN 'F1'
                    WHEN b.frequencia  = 4 THEN 'F2'
                    WHEN b.frequencia  = 3 THEN 'F3'
                    WHEN b.frequencia  = 2 THEN 'F4'
                    ELSE                        'F5'
                END
            ELSE  -- FARMACIAS (confirmado planilha Ribeiro, mai/2026)
                CASE
                    WHEN b.frequencia >= 7 THEN 'F1'
                    WHEN b.frequencia >= 5 THEN 'F2'
                    WHEN b.frequencia >= 3 THEN 'F3'
                    WHEN b.frequencia  = 2 THEN 'F4'
                    ELSE                        'F5'
                END
        END AS freq_bucket,

        -- Bucket Recência
        --   HOSPITALAR/SAC (validado contra planilha Alves):
        --     R1 <= 30d | R2 <= 60d | R3 <= 120d | R4 <= 180d | R5 > 180d
        --   FARMACIAS: mesmos thresholds (a confirmar)
        CASE
            WHEN b.rfv_familia IN ('HOSPITALAR', 'SAC') THEN
                CASE
                    WHEN b.recencia_dias <=  30 THEN 'R1'
                    WHEN b.recencia_dias <=  60 THEN 'R2'
                    WHEN b.recencia_dias <= 120 THEN 'R3'
                    WHEN b.recencia_dias <= 180 THEN 'R4'
                    ELSE                              'R5'
                END
            ELSE  -- FARMACIAS
                CASE
                    WHEN b.recencia_dias <=  30 THEN 'R1'
                    WHEN b.recencia_dias <=  60 THEN 'R2'
                    WHEN b.recencia_dias <= 120 THEN 'R3'
                    WHEN b.recencia_dias <= 180 THEN 'R4'
                    ELSE                              'R5'
                END
        END AS rec_bucket

    FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_base` b
)
SELECT
    s.*,
    CONCAT(s.freq_bucket, s.rec_bucket) AS classificacao_1,

    -- Segmento textual — nomenclatura exata da planilha Alves (11 segmentos)
    CASE CONCAT(s.freq_bucket, s.rec_bucket)
        WHEN 'F1R1' THEN 'Campeões'
        WHEN 'F1R2' THEN 'Fiéis'
        WHEN 'F1R3' THEN 'Fiéis'
        WHEN 'F1R4' THEN 'Não pode perder'
        WHEN 'F1R5' THEN 'Não pode perder'
        WHEN 'F2R1' THEN 'Fiéis'
        WHEN 'F2R2' THEN 'Fiéis'
        WHEN 'F2R3' THEN 'Fiéis'
        WHEN 'F2R4' THEN 'Em risco'
        WHEN 'F2R5' THEN 'Em risco'
        WHEN 'F3R1' THEN 'Fiéis em potencial'
        WHEN 'F3R2' THEN 'Fiéis em potencial'
        WHEN 'F3R3' THEN 'Precisando de atenção'
        WHEN 'F3R4' THEN 'Em risco'
        WHEN 'F3R5' THEN 'Em risco'
        WHEN 'F4R1' THEN 'Fiéis em potencial'
        WHEN 'F4R2' THEN 'Fiéis em potencial'
        WHEN 'F4R3' THEN 'Quase dormentes'
        WHEN 'F4R4' THEN 'Hibernando'
        WHEN 'F4R5' THEN 'Perdidos'
        WHEN 'F5R1' THEN 'Novos clientes'
        WHEN 'F5R2' THEN 'Promessas'
        WHEN 'F5R3' THEN 'Quase dormentes'
        WHEN 'F5R4' THEN 'Perdidos'
        WHEN 'F5R5' THEN 'Perdidos'
        ELSE 'Outros'
    END AS classificacao_2,

    -- Código numérico do segmento (ordem da planilha Alves: 1=melhor, 11=pior)
    --   1=Campeões | 2=Fiéis | 3=Fiéis em potencial | 4=Novos clientes
    --   5=Promessas | 6=Precisando de atenção | 7=Quase dormentes
    --   8=Não pode perder | 9=Em risco | 10=Hibernando | 11=Perdidos
    CASE CONCAT(s.freq_bucket, s.rec_bucket)
        WHEN 'F1R1' THEN 1   -- Campeões
        WHEN 'F1R2' THEN 2   -- Fiéis
        WHEN 'F1R3' THEN 2
        WHEN 'F2R1' THEN 2
        WHEN 'F2R2' THEN 2
        WHEN 'F2R3' THEN 2
        WHEN 'F3R1' THEN 3   -- Fiéis em potencial
        WHEN 'F3R2' THEN 3
        WHEN 'F4R1' THEN 3
        WHEN 'F4R2' THEN 3
        WHEN 'F5R1' THEN 4   -- Novos clientes
        WHEN 'F5R2' THEN 5   -- Promessas
        WHEN 'F3R3' THEN 6   -- Precisando de atenção
        WHEN 'F4R3' THEN 7   -- Quase dormentes
        WHEN 'F5R3' THEN 7
        WHEN 'F1R4' THEN 8   -- Não pode perder
        WHEN 'F1R5' THEN 8
        WHEN 'F2R4' THEN 9   -- Em risco
        WHEN 'F2R5' THEN 9
        WHEN 'F3R4' THEN 9
        WHEN 'F3R5' THEN 9
        WHEN 'F4R4' THEN 10  -- Hibernando
        WHEN 'F4R5' THEN 11  -- Perdidos
        WHEN 'F5R4' THEN 11
        WHEN 'F5R5' THEN 11
        ELSE 99
    END AS classificacao_3

FROM scored s;


-- -----------------------------------------------------------------------------
-- 5. silver_com_rfv_resumo
--    Sumário por família × vendedor × segmento (para validação rápida)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_resumo` AS
SELECT
    rfv_familia,
    rfv_salesperson,
    classificacao_2                 AS segmento,
    classificacao_3                 AS segmento_num,
    COUNT(DISTINCT partner_name)    AS qtd_clientes,
    ROUND(SUM(valor_total), 2)      AS faturamento_total,
    ROUND(AVG(valor_total), 2)      AS ticket_medio,
    ROUND(AVG(frequencia), 2)       AS frequencia_media,
    ROUND(AVG(recencia_dias), 1)    AS recencia_media_dias,
    CURRENT_DATE()                  AS data_referencia
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
GROUP BY
    rfv_familia,
    rfv_salesperson,
    classificacao_2,
    classificacao_3
ORDER BY
    rfv_familia,
    rfv_salesperson,
    classificacao_3;


-- -----------------------------------------------------------------------------
-- 6. param_com_vendedor_map
--    Mapeamento explícito rfv_salesperson → CRM user_id (Pipedrive)
--
--    PROBLEMA RESOLVIDO: JOIN por UPPER(name) falha para Kauã ('KAUA' ≠ 'KAUÃ RODRIGUES'),
--    Richard ('RICHARD' ≠ 'RICHARD SILVA') e Ribeiro ('RIBEIRO' ≠ 'CAUÃ RIBEIRO').
--    Usando user_id (PK imutável do Pipedrive) o match é sempre correto.
--
--    Para adicionar vendedor: inserir linha com rfv_salesperson = nome usado na carteira
--    e crm_user_id = user_id da tabela crm_raw.dim_crm_user.
--
--    user_ids confirmados em mai/2026 via tmp_crm_users.py:
--      Guilherme     → 24014421
--      Kaua          → 24336479  (CRM: "Kauã Rodrigues")
--      Richard       → 25975292  (CRM: "Richard Silva")
--      Ribeiro       → 25242560  (CRM: "Cauã Ribeiro")
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE `sapient-metrics-492914-m7.silver_comercial.param_com_vendedor_map` AS
SELECT 'Guilherme' AS rfv_salesperson, 24014421 AS crm_user_id, 'Guilherme'      AS crm_user_name
UNION ALL SELECT 'Ribeiro',   25242560, 'Cauã Ribeiro'
UNION ALL SELECT 'Kaua',      24336479, 'Kauã Rodrigues'
UNION ALL SELECT 'Richard',   25975292, 'Richard Silva'
UNION ALL SELECT 'Giovanna',  24298727, 'Geovana gomes'
UNION ALL SELECT 'Eduardo',   24014432, 'Eduardo'
UNION ALL SELECT 'Ramos',     26316303, 'Kauan Ramos';


-- -----------------------------------------------------------------------------
-- 7. param_com_entity_bridge
--    Tabela-ponte: partner_code (ERP) ↔ org_id (Pipedrive CRM)
--    É a chave de tudo no setor Comercial — permite cruzar pedidos ERP
--    com pipeline CRM, ligações GoTo (via vendedor), financeiro e RFV.
--
--    Hierarquia de match (executada por populate_entity_bridge.py):
--      1. CNPJ normalizado (dígitos apenas) — match exato
--      2. Nome do cliente fuzzy (WRatio >= 85) — match aproximado
--      3. Manual — inserção direta para casos especiais
--
--    GoTo não entra nesta ponte pelo lado do cliente (sem phone coverage).
--    Ligações GoTo são linkadas pelo VENDEDOR: goto_extensions.user_id
--    → crm_raw.dim_crm_user.user_id → deals.owner_id.
--
--    NOTA: um partner_code pode ter múltiplos org_id (filiais no Pipedrive).
--          Um org_id pode ter múltiplos partner_code (mesma empresa, CNPJs distintos).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge` (
    partner_code     INT64    NOT NULL,
    partner_name     STRING,
    tax_id           STRING,            -- CNPJ/CPF normalizado (só dígitos)
    org_id           INT64,             -- Pipedrive org_id (NULL = sem match CRM)
    org_name         STRING,            -- Nome no Pipedrive
    match_type       STRING,            -- 'cnpj_exact' | 'name_fuzzy' | 'manual' | 'unmatched'
    match_score      FLOAT64,           -- 100.0 = exact; 0-100 = fuzzy score
    is_active        BOOL,
    created_at       TIMESTAMP,
    updated_at       TIMESTAMP
);
