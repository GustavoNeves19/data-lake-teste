-- fact_serial_number | NÚMEROS SÉRIES (sem correções)
SELECT
    YCODITM AS item_code,
    YNUMSER AS serial_number,
    YNUMLOT AS batch_number,
    YUSASER AS is_in_use,
    YLOTINS AS inspection_batch,
    YSTAINS AS inspection_status,
    YPESINS AS inspection_weight,
    YRESINS AS inspection_result
FROM [NÚMEROS SÉRIES]
