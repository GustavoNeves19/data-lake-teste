-- fact_production_item | ITENS ORDENS PRODUÇÕES (sem correções)
SELECT
    YNUMERO AS prod_order_number,
    YCODITM AS item_code,
    YQTDITM AS planned_qty,
    YQTDREA AS actual_qty
FROM [ITENS ORDENS PRODUÇÕES]
