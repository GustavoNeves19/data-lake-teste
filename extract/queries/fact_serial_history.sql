-- fact_serial_history | HISTÓRICOS NÚMEROS SÉRIES (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YCODITM AS item_code,
    YNUMSER AS serial_number,
    YNUMERO AS document_number,
    YSTASER AS serial_status,
    YQTDSER AS quantity,
    YOBSNUM AS notes,
    YDATINC AS created_at_erp,
    YUSAINC AS created_by_erp,
    YDATEXC AS excluded_at
FROM [HISTÓRICOS NÚMEROS SÉRIES]
