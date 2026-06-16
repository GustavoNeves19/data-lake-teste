-- dim_company | EMPRESAS (já validado na 1ª carga)
SELECT
    YCODEMP AS company_code,
    YNOMEMP AS company_name,
    YCGCCPF AS tax_id,
    YINSRG  AS state_registration,
    YCIDEMP AS city,
    YESTEMP AS state,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active
FROM EMPRESAS
WHERE YDATEXC IS NULL
