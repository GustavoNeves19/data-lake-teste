-- bridge_item_bom | ITENS VINCULADOS (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YCODITM AS parent_item_code,
    YITMVIN AS child_item_code,
    YQTDVIN AS quantity,
    YTIPVIN AS link_type,
    YDATEXC AS excluded_at
FROM [ITENS VINCULADOS]
