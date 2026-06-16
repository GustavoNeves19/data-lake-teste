-- dim_department | SETORES (sem correções)
SELECT
    YCODSET AS department_code,
    YNOMSET AS department_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active
FROM SETORES
WHERE YDATEXC IS NULL
