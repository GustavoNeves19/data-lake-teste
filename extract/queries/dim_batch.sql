-- dim_batch | LOTES ESTOQUES
-- REESCRITO: tabela real tem estrutura de movimentação por lote,
-- não cadastro master. Colunas reais: YNUMLOT, YCODITM, YTIPMOV,
-- YDATMOV, YQTDMOV. Sem YCODEMP, YDATLOT, YDATVAL, YSLDITM.
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODITM AS item_code,
    YNUMLOT AS batch_number,
    YDATMOV AS batch_date,
    YQTDMOV AS batch_balance,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [LOTES ESTOQUES]
