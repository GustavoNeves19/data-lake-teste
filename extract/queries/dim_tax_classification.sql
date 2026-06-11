-- dim_tax_classification | CLASSIFICAÇÕES FISCAIS
-- Correção: YNCMCLA removido (não existe na tabela)
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODCLA AS tax_class_code,
    YNOMCLA AS tax_class_name,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM [CLASSIFICAÇÕES FISCAIS]
