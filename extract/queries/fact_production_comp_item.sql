-- fact_production_comp_item | Correção: nome da tabela completo
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YNUMERO AS prod_order_number,
    YCODITM AS item_code,
    YQTDITM AS planned_qty,
    YQTDREA AS actual_qty,
    YDATEXC AS excluded_at
FROM [ITENS COMPLEMENTARES ORDENS PRODUÇÕES]
