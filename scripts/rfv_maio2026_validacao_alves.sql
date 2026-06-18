/* ----------------------------------------------------------------------------
   RFV Maio/2026 direto no ERP (NSR_ERP)

   Calcula Recencia, Frequencia e Valor por cliente e a classificacao
   (Campeoes, Fieis, etc.) so com SQL, na origem. Somente leitura: cole no
   SSMS e rode (F5).

   Saidas:
     1) Faturamento do periodo (total e por familia)
     2) RFV geral por segmento
     3) RFV por familia
     4) Resumo (total + campeoes)

   Metodologia:
     Vendas faturadas .. YTIPOPE='S', YSTATUS IN (3,4), natureza YFINNAT<>'N'
     Faturamento ....... SUM(YVALPRO) (produto, sem imposto/frete)
     Janela ............ 12 meses ate o corte, pela data da nota (YDATNOT)
     Grupo do vendedor . YGRUVEN: FA=Hospitalar, FR=Farmacias, PC=SAC
     Fora .............. canal 000054 (Site-Loja)
     Frequencia ........ F1>=6, F2=5, F3=4, F4=2-3, F5<=1
     Recencia (dias) ... R1<=30, R2<=60, R3<=120, R4<=180, R5>180
     Campeao ........... F1R1

   Dois pontos de metodologia ficam como parametro no topo: canceladas e
   consolidacao de filiais.
   ---------------------------------------------------------------------------- */

SET NOCOUNT ON;

DECLARE @DataRef DATE = '2026-05-31';     -- corte (fechamento de maio)
DECLARE @IncluirCanceladas BIT = 0;       -- 0 = ignora nota cancelada (YDATEXC)
DECLARE @ConsolidarFiliais  BIT = 0;      -- 1 = junta matriz+filiais (CNPJ raiz)

DECLARE @JanelaIni DATE =
    DATEFROMPARTS(YEAR(DATEADD(YEAR,-1,@DataRef)), MONTH(DATEADD(YEAR,-1,@DataRef)), 1);

;WITH notas AS (
    SELECT
        REPLACE(REPLACE(REPLACE(REPLACE(ISNULL(cli.YCGCCPF,''),'.',''),'/',''),'-',''),' ','') AS doc,
        cv.YCODCLI                       AS code,
        UPPER(LTRIM(RTRIM(cli.YNOMCLI))) AS nome,
        CASE a.YGRUVEN WHEN 'FA' THEN 'HOSPITALAR' WHEN 'FR' THEN 'FARMACIAS' WHEN 'PC' THEN 'SAC' END AS familia,
        cv.YNUMERO                       AS pedido,
        cv.YVALPRO                       AS valor,
        cv.YDATPED                       AS data_pedido
    FROM [COMPRAS E VENDAS] cv
    LEFT JOIN [NATUREZAS DE OPERAÇÕES]   nat ON nat.YCODNAT = cv.YCODNAT
    LEFT JOIN [ATENDENTES]               a   ON a.YCODVEN   = cv.YCODVEN2
    LEFT JOIN [CLIENTES OU FORNECEDORES] cli ON cli.YCODCLI = cv.YCODCLI
    WHERE cv.YTIPOPE = 'S'
      AND nat.YFINNAT <> 'N'
      AND cv.YSTATUS IN (3, 4)
      AND cv.YCODVEN <> '000054'
      AND a.YGRUVEN IN ('FA', 'FR', 'PC')
      AND cv.YDATNOT BETWEEN @JanelaIni AND @DataRef
      AND (@IncluirCanceladas = 1 OR cv.YDATEXC IS NULL)
),
keyed AS (
    -- cliente: documento completo (cada CNPJ/CPF = 1). Sem doc valido, separa por codigo.
    SELECT
        CASE
            WHEN LEN(doc) NOT IN (11, 14)                 THEN 'COD:' + CAST(code AS VARCHAR(20))
            WHEN @ConsolidarFiliais = 1 AND LEN(doc) = 14 THEN LEFT(doc, 8)
            ELSE doc
        END AS cliente_id,
        nome, familia, pedido, valor, data_pedido
    FROM notas
),
base AS (
    SELECT
        cliente_id,
        familia,
        MIN(nome)                                 AS cliente_nome,
        COUNT(DISTINCT pedido)                    AS frequencia,
        SUM(valor)                                AS valor_total,
        DATEDIFF(DAY, MAX(data_pedido), @DataRef) AS recencia_dias
    FROM keyed
    GROUP BY cliente_id, familia
)
SELECT
    b.*,
    fr.f_bucket + fr.r_bucket AS celula,
    CASE fr.f_bucket + fr.r_bucket
        WHEN 'F1R1' THEN 'Campeões'
        WHEN 'F1R2' THEN 'Fiéis'              WHEN 'F1R3' THEN 'Fiéis'
        WHEN 'F1R4' THEN 'Não pode perder'    WHEN 'F1R5' THEN 'Não pode perder'
        WHEN 'F2R1' THEN 'Fiéis'              WHEN 'F2R2' THEN 'Fiéis'
        WHEN 'F2R3' THEN 'Fiéis'              WHEN 'F2R4' THEN 'Em risco'
        WHEN 'F2R5' THEN 'Em risco'
        WHEN 'F3R1' THEN 'Fiéis em potencial' WHEN 'F3R2' THEN 'Fiéis em potencial'
        WHEN 'F3R3' THEN 'Precisando de atenção'
        WHEN 'F3R4' THEN 'Em risco'           WHEN 'F3R5' THEN 'Em risco'
        WHEN 'F4R1' THEN 'Fiéis em potencial' WHEN 'F4R2' THEN 'Fiéis em potencial'
        WHEN 'F4R3' THEN 'Quase dormentes'    WHEN 'F4R4' THEN 'Hibernando'
        WHEN 'F4R5' THEN 'Perdidos'
        WHEN 'F5R1' THEN 'Novos clientes'     WHEN 'F5R2' THEN 'Promessas'
        WHEN 'F5R3' THEN 'Quase dormentes'    WHEN 'F5R4' THEN 'Perdidos'
        WHEN 'F5R5' THEN 'Perdidos'
        ELSE 'Outros'
    END AS segmento,
    CASE fr.f_bucket + fr.r_bucket
        WHEN 'F1R1' THEN 1
        WHEN 'F1R2' THEN 2  WHEN 'F1R3' THEN 2
        WHEN 'F2R1' THEN 2  WHEN 'F2R2' THEN 2  WHEN 'F2R3' THEN 2
        WHEN 'F3R1' THEN 3  WHEN 'F3R2' THEN 3
        WHEN 'F4R1' THEN 3  WHEN 'F4R2' THEN 3
        WHEN 'F5R1' THEN 4
        WHEN 'F5R2' THEN 5
        WHEN 'F3R3' THEN 6
        WHEN 'F4R3' THEN 7  WHEN 'F5R3' THEN 7
        WHEN 'F1R4' THEN 8  WHEN 'F1R5' THEN 8
        WHEN 'F2R4' THEN 9  WHEN 'F2R5' THEN 9
        WHEN 'F3R4' THEN 9  WHEN 'F3R5' THEN 9
        WHEN 'F4R4' THEN 10
        WHEN 'F4R5' THEN 11 WHEN 'F5R4' THEN 11 WHEN 'F5R5' THEN 11
        ELSE 99
    END AS segmento_num
INTO #rfv
FROM base b
CROSS APPLY (
    SELECT
        CASE WHEN b.frequencia <= 1 THEN 'F5'
             WHEN b.frequencia <= 3 THEN 'F4'
             WHEN b.frequencia <= 4 THEN 'F3'
             WHEN b.frequencia <= 5 THEN 'F2'
             ELSE 'F1' END AS f_bucket,
        CASE WHEN b.recencia_dias <=  30 THEN 'R1'
             WHEN b.recencia_dias <=  60 THEN 'R2'
             WHEN b.recencia_dias <= 120 THEN 'R3'
             WHEN b.recencia_dias <= 180 THEN 'R4'
             ELSE 'R5' END AS r_bucket
) fr;


-- 1) Faturamento do periodo. A soma das familias fecha no total geral.
--    Aqui familia = grupo do vendedor da nota, nao a carteira do cliente.
SELECT
    COALESCE(familia, 'TOTAL GERAL')        AS familia,
    COUNT(*)                                AS qtd_clientes,
    CAST(SUM(valor_total) AS DECIMAL(18,2)) AS faturamento
FROM #rfv
GROUP BY ROLLUP(familia)
ORDER BY GROUPING(familia), familia;


-- 2) RFV geral por segmento
SELECT
    segmento_num                            AS ordem,
    segmento,
    COUNT(*)                                AS qtd_clientes,
    CAST(SUM(valor_total) AS DECIMAL(18,2)) AS faturamento,
    CAST(100.0 * COUNT(*)         / SUM(COUNT(*))         OVER () AS DECIMAL(5,1)) AS pct_clientes,
    CAST(100.0 * SUM(valor_total) / SUM(SUM(valor_total)) OVER () AS DECIMAL(5,1)) AS pct_faturamento
FROM #rfv
GROUP BY segmento_num, segmento
ORDER BY segmento_num;


-- 3) RFV por familia
SELECT
    familia,
    segmento_num                            AS ordem,
    segmento,
    COUNT(*)                                AS qtd_clientes,
    CAST(SUM(valor_total) AS DECIMAL(18,2)) AS faturamento
FROM #rfv
GROUP BY familia, segmento_num, segmento
ORDER BY familia, segmento_num;


-- 4) Resumo: total + campeoes
SELECT
    @DataRef                                AS data_corte,
    @JanelaIni                              AS janela_ini,
    @DataRef                                AS janela_fim,
    COUNT(*)                                AS clientes_total,
    CAST(SUM(valor_total) AS DECIMAL(18,2)) AS faturamento_total,
    SUM(CASE WHEN segmento = 'Campeões' THEN 1 ELSE 0 END) AS campeoes_qtd,
    CAST(SUM(CASE WHEN segmento = 'Campeões' THEN valor_total ELSE 0 END) AS DECIMAL(18,2)) AS campeoes_faturamento
FROM #rfv;

DROP TABLE #rfv;
