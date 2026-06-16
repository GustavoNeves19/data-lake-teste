-- dim_partner | CLIENTES OU FORNECEDORES
-- Correções: YCGCCLI→YCGCCPF, YUFECLI→YESTCLI, YRAZCLI→YFANCLI,
--            YEMAIL→YEMAIL1, YTELCLI→YTE1CLI
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
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active
FROM [CLIENTES OU FORNECEDORES]
WHERE YDATEXC IS NULL
