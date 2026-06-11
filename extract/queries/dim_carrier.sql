-- dim_carrier | TRANSPORTADORAS
-- Correções: YCGCTRA→YCGCCPF, YUFTRA→YESTTRA
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODTRA AS carrier_code,
    YNOMTRA AS carrier_name,
    YCGCCPF AS tax_id,
    YCIDTRA AS city,
    YESTTRA AS state,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM TRANSPORTADORAS
