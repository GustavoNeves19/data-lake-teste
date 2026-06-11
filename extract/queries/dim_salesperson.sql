-- dim_salesperson | ATENDENTES
-- Cadastro de vendedores / representantes comerciais da Nevoni
-- YATIINA: 1 = ativo, 2 = inativo
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODVEN AS salesperson_code,
    YNOMVEN AS salesperson_name,
    NULLIF(YGRUVEN, '') AS salesperson_group_code,
    CASE WHEN YATIINA = 1 THEN 1 ELSE 0 END AS is_active,
    COALESCE(YDATALT, YDATINC) AS updated_at_erp,
    YDATEXC AS excluded_at
FROM ATENDENTES
