-- fact_production_order | ORDENS PRODUÇÕES (sem correções)
SELECT
    YNUMERO AS prod_order_number,
    YNUMPED AS order_number,
    YCODEMP AS company_code,
    YDATPED AS order_date,
    YDATPRE AS forecast_date,
    YSTAORD AS prod_status,
    YURGENT AS is_urgent,
    YDATBAI AS completed_at,
    YUSASOL AS requested_by,
    YOBSERV AS notes
FROM [ORDENS PRODUÇÕES]
WHERE YDATEXC IS NULL
