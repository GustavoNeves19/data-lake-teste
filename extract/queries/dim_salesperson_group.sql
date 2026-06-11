-- dim_salesperson_group | GRUPOS ATENDENTES
-- Grupos de vendedores (ex: FARMER, FARMER (ALVES))
-- Referenciado por ATENDENTES.YGRUVEN
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODGRU AS salesperson_group_code,
    YNOMGRU AS group_name,
    COALESCE(YDATALT, YDATINC) AS updated_at_erp,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [GRUPOS ATENDENTES]
