-- dim_payment_condition | CONDIÇÕES DE PAGAMENTOS (sem correções)
SELECT
    YCODPGT AS payment_cond_code,
    YNOMPGT AS payment_cond_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active
FROM [CONDIÇÕES DE PAGAMENTOS]
WHERE YDATEXC IS NULL
