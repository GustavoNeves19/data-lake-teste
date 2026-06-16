-- dim_operation_nature | NATUREZAS DE OPERAÇÕES (sem correções)
SELECT
    YCODNAT AS nature_code,
    YNOMNAT AS nature_name,
    YENTSAI AS direction,
    YVDASRV AS sale_or_service,
    YFINNAT AS financial_flag,
    YDEVNAT AS is_return,
    YTIPMOV AS stock_movement_type,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active
FROM [NATUREZAS DE OPERAÇÕES]
WHERE YDATEXC IS NULL