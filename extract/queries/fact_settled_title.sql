-- fact_settled_title | PAGAS E RECEBIDAS | Modelo MOVER (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YNUMERO AS title_number,
    YNUMPED AS order_number,
    YENCDES AS settlement_type,
    YCODCLI AS partner_code,
    YCODEMP AS company_code,
    YCODBCO AS bank_code,
    YDATEMI AS issue_date,
    YDATVEN AS due_date,
    YDATPAG AS payment_date,
    YVALDOC AS document_amount,
    YVALPAG AS paid_amount,
    YDATEXC AS excluded_at
FROM [PAGAS E RECEBIDAS]
