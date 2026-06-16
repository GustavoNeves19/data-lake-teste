-- fact_quote | ORÇAMENTOS (sem correções)
-- YTIPOPE 100%% vazio — sem filtro compra/venda
SELECT
    YNUMERO   AS quote_number,
    YTIPORC   AS quote_type,
    YSTATUS   AS quote_status,
    YSTAORC   AS detailed_status,
    YCODCLI   AS partner_code,
    YCODEMP   AS company_code,
    YCODTRA   AS carrier_code,
    YDATPED   AS quote_date,
    YDATENT   AS delivery_date,
    YCODNAT   AS nature_code,
    YCODPGT   AS payment_cond_code,
    YSOLICI   AS requester,
    YVALPRO   AS product_amount,
    YVALFRE   AS freight_amount,
    YVALTOT   AS total_amount,
    YOR1ENV   AS sent_date_1,
    YOR2ENV   AS sent_date_2,
    YINCOTERM AS incoterm,
    YFORPAG   AS payment_method,
    YDATINC   AS created_at_erp,
    YUSAINC   AS created_by_erp
FROM [ORÇAMENTOS]
WHERE YDATEXC IS NULL
