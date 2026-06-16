-- fact_receivable | PAGAR E RECEBER | YENCDES='D' (sem correções)
SELECT
    YNUMERO AS title_number,
    YNUMPED AS order_number,
    YCODCLI AS partner_code,
    YCODEMP AS company_code,
    YCODBCO AS bank_code,
    YDATEMI AS issue_date,
    YDATVEN AS due_date,
    YVALDOC AS document_amount,
    YVALLIQ AS net_amount
FROM [PAGAR E RECEBER]
WHERE YENCDES = 'D'
  AND YDATEXC IS NULL
