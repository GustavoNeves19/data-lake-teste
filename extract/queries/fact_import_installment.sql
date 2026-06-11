-- fact_import_installment | DESABILITADO
-- A tabela PROC. IMP. PARCELAS não foi encontrada no ERP.
-- Este SELECT retorna zero linhas propositalmente.
-- Quando a tabela correta for identificada, atualizar aqui.
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YIMPORT  AS import_number,
    YNUMPED  AS order_number,
    YNOMPAR  AS installment_name,
    YPERPAR  AS installment_pct,
    YDATPAR  AS installment_date,
    YVALPAR  AS installment_amount,
    YVALUSD  AS total_usd,
    YVALBRL  AS total_brl,
    YSPREAD  AS spread,
    YOBSPAR  AS installment_note,
    YDATEXC  AS excluded_at
FROM [PROCESSOS IMPORTAÇÕES PARCELAS PEDIDOS]
