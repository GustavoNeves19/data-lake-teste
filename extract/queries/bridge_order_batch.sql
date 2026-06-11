-- bridge_order_batch | LOTES COMPRAS E VENDAS (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YNUMPED AS order_number,
    YCODITM AS item_code,
    YNUMLOT AS batch_number,
    YQTDITM AS quantity,
    YDATLOT AS batch_date,
    YDATVAL AS expiration_date,
    YDATINC AS created_at_erp,
    YUSAINC AS created_by_erp,
    YDATEXC AS excluded_at
FROM [LOTES COMPRAS E VENDAS]
