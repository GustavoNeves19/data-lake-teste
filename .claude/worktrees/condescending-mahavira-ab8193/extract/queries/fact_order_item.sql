-- fact_order_item | ITENS COMPRAS E VENDAS + cabeçalho (sem correções)
SELECT
    itm.YNUMERO   AS order_number,
    cv.YTIPOPE    AS operation_type,
    itm.YCODITM   AS item_code,
    itm.YQTDITM   AS quantity,
    itm.YVALITM   AS unit_price,
    itm.YVALIPI   AS ipi_amount,
    itm.YVALICM   AS icms_amount,
    itm.YINSPECION AS inspection_flag
FROM [ITENS COMPRAS E VENDAS] itm
INNER JOIN [COMPRAS E VENDAS] cv ON itm.YNUMERO = cv.YNUMERO
WHERE cv.YDATEXC IS NULL
