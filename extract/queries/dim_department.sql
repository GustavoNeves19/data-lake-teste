-- dim_department | SETORES (sem correções)
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODSET AS department_code,
    YNOMSET AS department_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM SETORES
