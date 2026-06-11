-- dim_family | FAMÍLIAS (sem correções)
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODFAM AS family_code,
    YNOMFAM AS family_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [FAMÍLIAS]
