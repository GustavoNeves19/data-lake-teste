-- fact_import_installment | DESABILITADO
-- A tabela PROC. IMP. PARCELAS não foi encontrada no ERP.
-- Este SELECT retorna zero linhas propositalmente.
-- Quando a tabela correta for identificada, atualizar aqui.
SELECT
    YIMPORT  AS import_number,
    YNUMPED  AS order_number,
    YNOMPAR  AS installment_name,
    YPERPAR  AS installment_pct,
    YDATPAR  AS installment_date,
    YVALPAR  AS installment_amount,
    YVALUSD  AS total_usd,
    YVALBRL  AS total_brl,
    YSPREAD  AS spread,
    YOBSPAR AS installment_note
FROM [PROCESSOS IMPORTAÇÕES PARCELAS PEDIDOS]
WHERE YDATEXC IS NULL
