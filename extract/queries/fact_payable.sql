-- fact_payable | PAGAR E RECEBER | YENCDES='E' (sem correções)
SELECT
    YNUMERO AS title_number,
    YNUMPED AS order_number,
    YCODCLI AS partner_code,
    YCODEMP AS company_code,
    YCODBCO AS bank_code,
    YCODSET AS department_code,
    YDATEMI AS issue_date,
    YDATVEN AS due_date,
    YVALDOC AS document_amount,
    YVALLIQ AS net_amount,
    YCODOS1 AS surcharge_code_1,
    YVALOS1 AS surcharge_amount_1,
    YCODOS2 AS surcharge_code_2,
    YVALOS2 AS surcharge_amount_2,
    YCODOS3 AS surcharge_code_3,
    YVALOS3 AS surcharge_amount_3,
    YDATINC AS created_at_erp,
    YDATEXC AS excluded_at
FROM [PAGAR E RECEBER]
WHERE YENCDES = 'E'              -- partição de domínio (a pagar). Filtro YDATEXC vive no silver.
