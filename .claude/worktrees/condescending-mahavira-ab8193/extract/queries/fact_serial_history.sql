-- fact_serial_history | HISTÓRICOS NÚMEROS SÉRIES (sem correções)
SELECT
    YCODITM AS item_code,
    YNUMSER AS serial_number,
    YNUMERO AS document_number,
    YSTASER AS serial_status,
    YQTDSER AS quantity,
    YOBSNUM AS notes,
    YDATINC AS created_at_erp,
    YUSAINC AS created_by_erp
FROM [HISTÓRICOS NÚMEROS SÉRIES]
