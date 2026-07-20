-- dim_item | ITENS
-- Correções: YCODFAM→YFAMITM, YCODGRU→YGRPITM, YCODCLA→YCLAITM,
--            YPESLIQ→YLIQITM, YPESBRU→YBRUITM
-- Bronze pura: traz ativos + excluídos. Filtro YDATEXC vive no silver.
SELECT
    YCODITM AS item_code,
    YNOMITM AS item_name,
    YDISITM AS item_description,
    YUNDITM AS unit_code,
    YFAMITM AS family_code,
    YGRPITM AS group_code,
    YCLAITM AS tax_class_code,
    YVALITMVIN AS linked_items_cost,
    YLIQITM AS net_weight,
    YBRUITM AS gross_weight,
    CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END AS is_active,
    YDATEXC AS excluded_at
FROM ITENS
