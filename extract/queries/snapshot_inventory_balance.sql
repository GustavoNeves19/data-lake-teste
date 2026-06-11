-- snapshot_inventory_balance | SALDOS EMPRESAS (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YCODEMP AS company_code,
    YCODITM AS item_code,
    YSLDITM AS general_balance,
    YSLDCPA AS purchase_balance,
    YSLDVDA AS sales_balance,
    YSLDDIS AS available_balance,
    YSLDTRA AS in_transit_balance,
    YDATEXC AS excluded_at
FROM [SALDOS EMPRESAS]
