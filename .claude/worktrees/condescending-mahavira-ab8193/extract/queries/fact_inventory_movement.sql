-- fact_inventory_movement | Correções:
--   Tabelas: MOVIMENTAÇÕES ESTOQUES + ITENS MOVIMENTAÇÕES ESTOQUES
--   YDATMOV está nos ITENS, não no cabeçalho
SELECT
    mov.YNUMERO AS movement_number,
    mov.YNUMPED AS order_number,
    mov.YTIPOPE AS operation_type,
    mov.YCODNAT AS nature_code,
    itm.YCODITM AS item_code,
    mov.YCODEMP AS company_code,
    itm.YDATMOV AS movement_date,
    itm.YQTDITM AS quantity,
    itm.YVALITM AS unit_price,
    itm.YNUMLOT AS batch_number
FROM [MOVIMENTAÇÕES ESTOQUES] mov
INNER JOIN [ITENS MOVIMENTAÇÕES ESTOQUES] itm ON mov.YNUMERO = itm.YNUMERO
WHERE mov.YDATEXC IS NULL
