-- fact_serial_number | NÚMEROS SÉRIES (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YCODITM AS item_code,
    YNUMSER AS serial_number,
    YNUMLOT AS batch_number,
    YUSASER AS is_in_use,
    YLOTINS AS inspection_batch,
    YSTAINS AS inspection_status,
    YPESINS AS inspection_weight,
    YRESINS AS inspection_result,
    YDATEXC AS excluded_at
FROM [NÚMEROS SÉRIES]
