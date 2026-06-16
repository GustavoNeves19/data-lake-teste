-- bridge_order_batch | LOTES COMPRAS E VENDAS (sem correções)
SELECT
    YNUMPED AS order_number,
    YCODITM AS item_code,
    YNUMLOT AS batch_number,
    YQTDITM AS quantity,
    YDATLOT AS batch_date,
    YDATVAL AS expiration_date,
    YDATINC AS created_at_erp,
    YUSAINC AS created_by_erp
FROM [LOTES COMPRAS E VENDAS]
