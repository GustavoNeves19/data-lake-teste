-- ════════════════════════════════════════════════════════════════════════════
-- RFV MAIO/2026 — Queries para o Alves (T-SQL / NSR_ERP)
-- ════════════════════════════════════════════════════════════════════════════
-- Janela:     2025-05-01 a 2026-05-31  (12 meses por DATA DA NOTA, yDatNot)
-- Filtros canônicos validados em Abril/2026 (Δ +0,047% vs BQ silver):
--   • yTipOpe = 'S'        → só vendas
--   • yFinNat <> 'N'       → exclui devoluções/categorias administrativas
--   • YGRUVEN IN ('FA','FR','PC')  → 3 grupos do RFV (sem e-commerce 'EC')
--   • YDATEXC IS NULL      → exclui notas canceladas
--   • yDatNot BETWEEN ...  → janela por data da NF emitida
--
-- Cliente único pode ser contado por:
--   • YCODCLI   = código do cliente (separa filiais por CNPJ)
--   • YNOMCLI   = razão social completa (agrupa filiais, mais preciso)
--   • YFANCLI   = nome fantasia (Alves usa esse na planilha; truncado ~26 chr)
-- ════════════════════════════════════════════════════════════════════════════


-- ────────────────────────────────────────────────────────────────────────────
-- 1) FATURAMENTO TOTAL (Geral — denominador comum)
-- ────────────────────────────────────────────────────────────────────────────
SELECT
    COUNT(*)                                                   AS qtd_notas,
    COUNT(DISTINCT a.YCODCLI)                                  AS clientes_por_codigo,
    COUNT(DISTINCT UPPER(LTRIM(RTRIM(cli.YNOMCLI))))           AS clientes_por_nome,
    SUM(a.yValPro)                                             AS faturamento_produto,
    SUM(a.yValTot)                                             AS faturamento_total
FROM [COMPRAS E VENDAS] a
LEFT JOIN [NATUREZAS DE OPERAÇÕES]      b   ON a.yCodNat   = b.yCodNat
LEFT JOIN [ATENDENTES]                  c   ON a.yCodVen2  = c.yCodVen
LEFT JOIN [CLIENTES OU FORNECEDORES]    cli ON cli.YCODCLI = a.YCODCLI
WHERE a.yTipOpe = 'S'
  AND b.yFinNat <> 'N'
  AND a.yDatNot BETWEEN '2025-05-01' AND '2026-05-31'
  AND c.YGRUVEN IN ('FA','FR','PC')
  AND a.YDATEXC IS NULL;


-- ────────────────────────────────────────────────────────────────────────────
-- 2) FATURAMENTO POR FAMÍLIA (soma deve bater com a query 1)
-- ────────────────────────────────────────────────────────────────────────────
SELECT
    c.YGRUVEN                                                  AS grupo_codigo,
    d.yNomGru                                                  AS familia,
    SUM(a.yValPro)                                             AS faturamento_produto,
    SUM(a.yValTot)                                             AS faturamento_total
FROM [COMPRAS E VENDAS] a
LEFT JOIN [NATUREZAS DE OPERAÇÕES]      b ON a.yCodNat  = b.yCodNat
LEFT JOIN [ATENDENTES]                  c ON a.yCodVen2 = c.yCodVen
LEFT JOIN [GRUPOS ATENDENTES]           d ON c.YGRUVEN  = d.YCODGRU
WHERE a.yTipOpe = 'S'
  AND b.yFinNat <> 'N'
  AND a.yDatNot BETWEEN '2025-05-01' AND '2026-05-31'
  AND c.YGRUVEN IN ('FA','FR','PC')
  AND a.YDATEXC IS NULL
GROUP BY c.YGRUVEN, d.yNomGru
ORDER BY faturamento_total DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- 3) QUANTIDADE DE CLIENTES + FATURAMENTO POR FAMÍLIA
-- ────────────────────────────────────────────────────────────────────────────
SELECT
    c.YGRUVEN                                                  AS grupo_codigo,
    d.yNomGru                                                  AS familia,
    COUNT(*)                                                   AS qtd_notas,
    COUNT(DISTINCT a.YCODCLI)                                  AS clientes_por_codigo,
    COUNT(DISTINCT UPPER(LTRIM(RTRIM(cli.YNOMCLI))))           AS clientes_por_nome,
    SUM(a.yValPro)                                             AS faturamento_produto,
    SUM(a.yValTot)                                             AS faturamento_total
FROM [COMPRAS E VENDAS] a
LEFT JOIN [NATUREZAS DE OPERAÇÕES]      b   ON a.yCodNat   = b.yCodNat
LEFT JOIN [ATENDENTES]                  c   ON a.yCodVen2  = c.yCodVen
LEFT JOIN [GRUPOS ATENDENTES]           d   ON c.YGRUVEN   = d.YCODGRU
LEFT JOIN [CLIENTES OU FORNECEDORES]    cli ON cli.YCODCLI = a.YCODCLI
WHERE a.yTipOpe = 'S'
  AND b.yFinNat <> 'N'
  AND a.yDatNot BETWEEN '2025-05-01' AND '2026-05-31'
  AND c.YGRUVEN IN ('FA','FR','PC')
  AND a.YDATEXC IS NULL
GROUP BY c.YGRUVEN, d.yNomGru
ORDER BY faturamento_total DESC;


-- ────────────────────────────────────────────────────────────────────────────
-- 4) DETALHE POR FAMÍLIA E VENDEDOR (a soma de cada grupo deve bater com query 3)
-- ────────────────────────────────────────────────────────────────────────────
SELECT
    c.YGRUVEN                                                  AS grupo_codigo,
    d.yNomGru                                                  AS familia,
    c.YCODVEN                                                  AS vendedor_codigo,
    UPPER(LTRIM(RTRIM(c.yNomVen)))                             AS vendedor_nome,
    COUNT(*)                                                   AS qtd_notas,
    COUNT(DISTINCT a.YCODCLI)                                  AS clientes_por_codigo,
    COUNT(DISTINCT UPPER(LTRIM(RTRIM(cli.YNOMCLI))))           AS clientes_por_nome,
    SUM(a.yValPro)                                             AS faturamento_produto,
    SUM(a.yValTot)                                             AS faturamento_total
FROM [COMPRAS E VENDAS] a
LEFT JOIN [NATUREZAS DE OPERAÇÕES]      b   ON a.yCodNat   = b.yCodNat
LEFT JOIN [ATENDENTES]                  c   ON a.yCodVen2  = c.yCodVen
LEFT JOIN [GRUPOS ATENDENTES]           d   ON c.YGRUVEN   = d.YCODGRU
LEFT JOIN [CLIENTES OU FORNECEDORES]    cli ON cli.YCODCLI = a.YCODCLI
WHERE a.yTipOpe = 'S'
  AND b.yFinNat <> 'N'
  AND a.yDatNot BETWEEN '2025-05-01' AND '2026-05-31'
  AND c.YGRUVEN IN ('FA','FR','PC')
  AND a.YDATEXC IS NULL
GROUP BY c.YGRUVEN, d.yNomGru, c.YCODVEN, UPPER(LTRIM(RTRIM(c.yNomVen)))
ORDER BY c.YGRUVEN, faturamento_total DESC;
