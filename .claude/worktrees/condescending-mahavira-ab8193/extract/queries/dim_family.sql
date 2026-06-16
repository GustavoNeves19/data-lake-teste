-- dim_family | FAMÍLIAS (sem correções)
SELECT
    YCODFAM AS family_code,
    YNOMFAM AS family_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active
FROM [FAMÍLIAS]
WHERE YDATEXC IS NULL
