-- dim_bank | BANCOS (sem correções)
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODBCO AS bank_code,
    YNOMBCO AS bank_name,
    YNUMBCO AS febraban_code,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM BANCOS
