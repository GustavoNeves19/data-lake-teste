-- dim_payment_condition | CONDIÇÕES DE PAGAMENTOS (sem correções)
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODPGT AS payment_cond_code,
    YNOMPGT AS payment_cond_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [CONDIÇÕES DE PAGAMENTOS]
