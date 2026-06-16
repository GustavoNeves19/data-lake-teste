-- fact_production_comp_item | Correção: nome da tabela completo
SELECT
    YNUMERO AS prod_order_number,
    YCODITM AS item_code,
    YQTDITM AS planned_qty,
    YQTDREA AS actual_qty
FROM [ITENS COMPLEMENTARES ORDENS PRODUÇÕES]
