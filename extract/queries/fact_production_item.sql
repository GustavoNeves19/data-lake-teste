-- fact_production_item | ITENS ORDENS PRODUÇÕES (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YNUMERO AS prod_order_number,
    YCODITM AS item_code,
    YQTDITM AS planned_qty,
    YQTDREA AS actual_qty,
    YDATEXC AS excluded_at
FROM [ITENS ORDENS PRODUÇÕES]
