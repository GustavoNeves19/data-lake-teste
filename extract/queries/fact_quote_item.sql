-- fact_quote_item | ITENS ORÇAMENTOS (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YNUMERO AS quote_number,
    YCODITM AS item_code,
    YQTDITM AS quantity,
    YVALITM AS unit_price,
    YIPIITM AS ipi_rate,
    YDATENT AS item_delivery_date,
    YDATEXC AS excluded_at
FROM [ITENS ORÇAMENTOS]
