-- ============================================================================
-- RFV COMPLETO DIRETO NO ERP (NSR_ERP) -- classificacao + valor, sem Data Lake
-- ============================================================================
-- Objetivo: provar que o RFV (campeoes, fieis, etc.) pode ser calculado 100%
-- dentro do ERP, em uma unica passada de SQL, e servir de FONTE DA VERDADE para
-- comparar com a planilha do Alves e com o dashboard (silver_com_rfv_score).
--
-- Esta query e a mesma metodologia do silver (build_silver_comercial.sql),
-- so que executada na origem. Mesmos filtros, mesmos buckets, mesmo grao.
-- Se rodar com a MESMA data de corte do dashboard, os numeros sao identicos.
--
-- O segredo do "bate imagem de outro tempo": tudo depende da DATA DE CORTE.
-- Por isso ela e um parametro explicito aqui (@DataRef). Fixe a mesma data nos
-- tres lugares (planilha / ERP / dashboard) e a divergencia de tempo some.
--
-- Grao: cliente (por NOME, consolidando filiais) x familia (FA/FR/PC).
--   Um cliente que compra em duas familias aparece nas duas (igual ao silver).
--
-- Filtros canonicos (validados abril->junho/2026, identicos ao silver):
--   YTIPOPE='S' . YFINNAT<>'N' . YDATEXC IS NULL (exclui canceladas) .
--   YSTATUS IN (3,4) . canal YCODVEN<>'000054' (Site-Loja) .
--   YGRUVEN IN ('FA','FR','PC')
-- Janela: 12 meses moveis terminando em @DataRef, por DATA DA NOTA (YDATNOT).
-- Recencia: dias desde a ultima DATA DE PEDIDO (YDATPED), igual ao silver.
-- Valor:    SUM(YVALPRO) (valor de produto / liquido, o mesmo da planilha).
-- Frequencia: COUNT(DISTINCT YNUMERO) (numero de pedidos distintos).
-- ============================================================================

-- ============================================================================
-- RESULTADO VALIDADO (corte 31/05/2026, rodado contra NSR_ERP em 17/06/2026):
--   GERAL: 1.691 clientes . R$ 9.957.156,37 . 45 campeoes (R$ 4.660.213,44)
--   (regra NOVA pos-15/06: canceladas EXCLUIDas via YDATEXC IS NULL)
--
--   Removendo o filtro de canceladas (regra ANTIGA, igual ao snapshot do
--   dashboard de 31/05): faturamento = R$ 10.095.774,05 -> BATE AO CENTAVO com
--   o BigQuery (silver_com_rfv_score) e com o numero Nevoni (R$ 10.095.887).
--
--   Diferenca que SOBRA vs dashboard (1.699 vs 1.564 clientes / 46 vs 53
--   campeoes): NAO e erro de calculo. E a CONSOLIDACAO DE FILIAIS. O dashboard
--   agrupa cliente pelo nome canonico da carteira (param_com_rfv_carteira:
--   filiais White Martins = 1 cliente); esta query agrupa pelo YNOMCLI cru, que
--   nao funde variantes do mesmo grupo. Consolidar funde linhas e empilha
--   frequencia -> menos clientes, mais campeoes. O valor nao muda (soma igual).
--
--   LICAO: o ERP fecha 100% o FATURAMENTO sozinho. A CLASSIFICACAO RFV
--   (campeoes) exige a regra de "cliente unico", que hoje so existe no Data
--   Lake. Para o ERP virar fonte da verdade tambem do RFV, falta levar esse
--   mapeamento de filiais para o ERP (tabela de-para) ou mante-lo no Data Lake.
-- ============================================================================

SET NOCOUNT ON;

-- ----------------------------------------------------------------------------
-- PARAMETRO: data de corte. Hoje = espelha o dashboard ao vivo.
-- Para reproduzir um numero historico (ex.: fechamento Maio/2026), fixe a data.
-- ----------------------------------------------------------------------------
DECLARE @DataRef DATE = CAST(GETDATE() AS DATE);
-- SET @DataRef = '2026-05-31';   -- <- descomente para travar um corte historico

DECLARE @JanelaIni DATE =
    DATEFROMPARTS(YEAR(DATEADD(YEAR, -1, @DataRef)), MONTH(DATEADD(YEAR, -1, @DataRef)), 1);
DECLARE @JanelaFim DATE = @DataRef;

-- ============================================================================
-- 1) BASE: agrega por cliente (nome) x familia dentro da janela
-- ============================================================================
;WITH base AS (
    SELECT
        UPPER(LTRIM(RTRIM(cli.YNOMCLI)))                     AS cliente,
        a.YGRUVEN                                           AS grupo,
        CASE a.YGRUVEN
            WHEN 'FA' THEN 'HOSPITALAR'
            WHEN 'FR' THEN 'FARMACIAS'
            WHEN 'PC' THEN 'SAC'
        END                                                 AS familia,
        COUNT(DISTINCT cv.YNUMERO)                          AS frequencia,
        SUM(cv.YVALPRO)                                     AS valor_total,
        MAX(cv.YDATPED)                                     AS ultima_compra,
        DATEDIFF(DAY, MAX(cv.YDATPED), @DataRef)            AS recencia_dias
    FROM [COMPRAS E VENDAS] cv
    LEFT JOIN [NATUREZAS DE OPERAÇÕES]   nat ON nat.YCODNAT = cv.YCODNAT
    LEFT JOIN [ATENDENTES]               a   ON a.YCODVEN   = cv.YCODVEN2
    LEFT JOIN [CLIENTES OU FORNECEDORES] cli ON cli.YCODCLI = cv.YCODCLI
    WHERE cv.YTIPOPE  = 'S'
      AND nat.YFINNAT <> 'N'
      AND cv.YDATEXC IS NULL
      AND cv.YSTATUS IN (3, 4)
      AND cv.YCODVEN <> '000054'
      AND a.YGRUVEN  IN ('FA', 'FR', 'PC')
      AND cv.YDATNOT >= @JanelaIni
      AND cv.YDATNOT <= @JanelaFim
      -- Opcional (visao "como a tela mostra"): tira licitacao do Eduardo.
      -- AND a.YNOMVEN NOT LIKE 'EDUARDO%'
    GROUP BY UPPER(LTRIM(RTRIM(cli.YNOMCLI))), a.YGRUVEN
),

-- ============================================================================
-- 2) SCORED: aplica os buckets F e R (regua oficial do Alves, 16/06/2026)
-- ============================================================================
scored AS (
    SELECT b.*,
        -- Frequencia: F5<=1 . F4<=3 . F3<=4 . F2<=5 . F1>=6
        CASE
            WHEN b.frequencia <= 1 THEN 'F5'
            WHEN b.frequencia <= 3 THEN 'F4'
            WHEN b.frequencia <= 4 THEN 'F3'
            WHEN b.frequencia <= 5 THEN 'F2'
            ELSE                        'F1'
        END AS f_bucket,
        -- Recencia: R1<=30 . R2<=60 . R3<=120 . R4<=180 . R5>180
        CASE
            WHEN b.recencia_dias <=  30 THEN 'R1'
            WHEN b.recencia_dias <=  60 THEN 'R2'
            WHEN b.recencia_dias <= 120 THEN 'R3'
            WHEN b.recencia_dias <= 180 THEN 'R4'
            ELSE                             'R5'
        END AS r_bucket
    FROM base b
)

-- ============================================================================
-- 3) #rfv: celula F#R# -> segmento textual + numero (1=melhor .. 11=pior)
--    Materializa numa tabela temporaria porque uma CTE so vale para o 1o SELECT
--    e aqui ha tres saidas. Nomenclatura identica a planilha do Alves / silver.
-- ============================================================================
SELECT s.*,
    s.f_bucket + s.r_bucket AS celula,
    CASE s.f_bucket + s.r_bucket
        WHEN 'F1R1' THEN 'Campeões'
        WHEN 'F1R2' THEN 'Fiéis'
        WHEN 'F1R3' THEN 'Fiéis'
        WHEN 'F1R4' THEN 'Não pode perder'
        WHEN 'F1R5' THEN 'Não pode perder'
        WHEN 'F2R1' THEN 'Fiéis'
        WHEN 'F2R2' THEN 'Fiéis'
        WHEN 'F2R3' THEN 'Fiéis'
        WHEN 'F2R4' THEN 'Em risco'
        WHEN 'F2R5' THEN 'Em risco'
        WHEN 'F3R1' THEN 'Fiéis em potencial'
        WHEN 'F3R2' THEN 'Fiéis em potencial'
        WHEN 'F3R3' THEN 'Precisando de atenção'
        WHEN 'F3R4' THEN 'Em risco'
        WHEN 'F3R5' THEN 'Em risco'
        WHEN 'F4R1' THEN 'Fiéis em potencial'
        WHEN 'F4R2' THEN 'Fiéis em potencial'
        WHEN 'F4R3' THEN 'Quase dormentes'
        WHEN 'F4R4' THEN 'Hibernando'
        WHEN 'F4R5' THEN 'Perdidos'
        WHEN 'F5R1' THEN 'Novos clientes'
        WHEN 'F5R2' THEN 'Promessas'
        WHEN 'F5R3' THEN 'Quase dormentes'
        WHEN 'F5R4' THEN 'Perdidos'
        WHEN 'F5R5' THEN 'Perdidos'
        ELSE 'Outros'
    END AS segmento,
    CASE s.f_bucket + s.r_bucket
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
FROM scored s;

-- ============================================================================
-- SAIDA 1) GERAL: classificacao por segmento (clientes + valor + %)
-- ============================================================================
SELECT
    segmento_num                                                AS ordem,
    segmento,
    COUNT(*)                                                    AS qtd_clientes,
    CAST(SUM(valor_total) AS DECIMAL(18,2))                     AS valor_total,
    CAST(100.0 * COUNT(*)        / SUM(COUNT(*))        OVER () AS DECIMAL(5,1)) AS pct_clientes,
    CAST(100.0 * SUM(valor_total) / SUM(SUM(valor_total)) OVER () AS DECIMAL(5,1)) AS pct_valor
FROM #rfv
GROUP BY segmento_num, segmento
ORDER BY segmento_num;

-- ============================================================================
-- SAIDA 2) POR FAMILIA: mesma classificacao, quebrada por HOSPITALAR/FARMACIAS/SAC
-- ============================================================================
SELECT
    familia,
    segmento_num                                                AS ordem,
    segmento,
    COUNT(*)                                                    AS qtd_clientes,
    CAST(SUM(valor_total) AS DECIMAL(18,2))                     AS valor_total
FROM #rfv
GROUP BY familia, segmento_num, segmento
ORDER BY familia, segmento_num;

-- ============================================================================
-- SAIDA 3) HEADLINE: total geral + recorte de CAMPEOES (a pergunta do Gustavo)
-- ============================================================================
SELECT
    @DataRef                                                    AS data_corte,
    @JanelaIni                                                  AS janela_ini,
    @JanelaFim                                                  AS janela_fim,
    COUNT(*)                                                    AS clientes_total,
    CAST(SUM(valor_total) AS DECIMAL(18,2))                     AS valor_total,
    SUM(CASE WHEN segmento = 'Campeões' THEN 1 ELSE 0 END)      AS campeoes_qtd,
    CAST(SUM(CASE WHEN segmento = 'Campeões' THEN valor_total ELSE 0 END) AS DECIMAL(18,2)) AS campeoes_valor
FROM #rfv;

DROP TABLE #rfv;
