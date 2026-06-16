-- dim_group | GRUPOS (sem correções)
SELECT
    YCODGRU AS group_code,
    YNOMGRU AS group_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active
FROM GRUPOS
WHERE YDATEXC IS NULL
