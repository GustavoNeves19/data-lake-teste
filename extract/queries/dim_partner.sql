-- dim_partner | CLIENTES OU FORNECEDORES
-- Correções: YCGCCLI→YCGCCPF, YUFECLI→YESTCLI, YRAZCLI→YFANCLI,
--            YEMAIL→YEMAIL1, YTELCLI→YTE1CLI
--
-- NOTA (28/05/2026): trazer TODOS os clientes (ativos + excluídos), porque o ERP
-- marca como YDATEXC NOT NULL clientes que pararam de comprar mas mantém o
-- histórico de vendas referenciando esses códigos. Filtrar YDATEXC IS NULL aqui
-- reduziu cobertura para ~12% no BQ — dos 17.124 clientes que compraram em
-- abr/25-abr/26, 12.445 (73%) estavam "excluídos". A flag is_active continua
-- separando ativos de não-ativos para queries que precisam.
SELECT
    YCODCLI AS partner_code,
    YTIPCLI AS partner_type,
    YNOMCLI AS partner_name,
    YFANCLI AS legal_name,
    YCGCCPF AS tax_id,
    YATICLI AS activity_type,
    YSITCLI AS status,
    YCIDCLI AS city,
    YESTCLI AS state,
    YPAICLI AS country,
    YEMAIL1 AS email,
    YTE1CLI AS phone,
    YCARCOM AS carteira_code,                       -- carteira comercial do cliente (CA..CF):
                                                    -- FONTE DA VERDADE da RFV (vendedor titular dono
                                                    -- do cliente). Substitui a param_com_rfv_carteira manual.
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [CLIENTES OU FORNECEDORES]
