-- dim_financial_item | ITENS FINANCEIROS (sem correções)
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODITM AS financial_item_code,
    YNOMITM AS financial_item_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [ITENS FINANCEIROS]
