-- bridge_item_bom | ITENS VINCULADOS (sem correções)
SELECT
    YCODITM AS parent_item_code,
    YITMVIN AS child_item_code,
    YQTDVIN AS quantity,
    YTIPVIN AS link_type
FROM [ITENS VINCULADOS]
