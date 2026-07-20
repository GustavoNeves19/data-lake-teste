-- fact_order_item | ITENS COMPRAS E VENDAS + cabeçalho (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver (item herda cancelamento do cabeçalho).
-- unit_cost (YVALCUS): custo médio ponderado calculado pelo próprio ERP no momento da
-- venda. 0 significa "não calculado" (YSTACUS nulo), não "custo zero" — tratar no silver/gold.
SELECT
    itm.YNUMERO   AS order_number,
    cv.YTIPOPE    AS operation_type,
    itm.YCODITM   AS item_code,
    itm.YQTDITM   AS quantity,
    itm.YVALITM   AS unit_price,
    itm.YVALIPI   AS ipi_amount,
    itm.YVALICM   AS icms_amount,
    itm.YVALCUS   AS unit_cost,
    itm.YINSPECION AS inspection_flag,
    cv.YDATEXC    AS excluded_at
FROM [ITENS COMPRAS E VENDAS] itm
INNER JOIN [COMPRAS E VENDAS] cv ON itm.YNUMERO = cv.YNUMERO
