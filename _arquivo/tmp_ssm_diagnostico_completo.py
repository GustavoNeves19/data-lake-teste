"""
Diagnóstico completo no NSR_ERP dos 82 clientes Hospitalar faltantes.

Roda 3 queries no SQL Server e consolida em um Excel:
  Q1: [CLIENTES OU FORNECEDORES] — localiza YCODCLI por LIKE no nome
  Q2: [COMPRAS E VENDAS]         — pedidos no período RFV-abril
  Q3: [PAGAR E RECEBER]          — títulos financeiros gerados desses pedidos
"""
import io, os, sys, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni')

import pandas as pd
from extract.sqlserver import SQLServerExtractor

os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')
from google.cloud import bigquery


def norm(s):
    if s is None or pd.isna(s): return ''
    s = str(s).upper().strip()
    s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', s)


# ── 1. Identificar os 82 faltantes (planilha Alves x carteira BQ HOSPITALAR) ──
xlsx = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026.xlsx'
plan = pd.read_excel(xlsx, sheet_name='Sem fórmula Geral')
plan['nome_norm'] = plan['ID - CLIENTE'].apply(norm)

bq = bigquery.Client(project='sapient-metrics-492914-m7', location='us-east1')
cart = bq.query("""
SELECT partner_name
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
WHERE is_active = TRUE AND rfv_familia = 'HOSPITALAR'
""").to_dataframe()
cart_norm = set(cart['partner_name'].apply(norm))

faltantes = plan[~plan['nome_norm'].isin(cart_norm)].copy()
nomes = faltantes['ID - CLIENTE'].dropna().tolist()
print(f'[setup] 82 faltantes identificados: {len(nomes)}')


# ── 2. Rodar queries no SQL Server ────────────────────────────────────────────
with SQLServerExtractor() as ext:
    cur = ext._conn.cursor()

    # ── Q1: localizar YCODCLI por LIKE
    print('\n[Q1] populando #nomes_busca e fazendo LIKE em [CLIENTES OU FORNECEDORES]...')
    cur.execute("IF OBJECT_ID('tempdb..#nomes_busca') IS NOT NULL DROP TABLE #nomes_busca")
    cur.execute("CREATE TABLE #nomes_busca (nome NVARCHAR(255))")
    cur.fast_executemany = True
    cur.executemany("INSERT INTO #nomes_busca (nome) VALUES (?)", [(n,) for n in nomes])
    ext._conn.commit()

    cur.execute("""
        SELECT DISTINCT
            nb.nome          AS nome_planilha,
            c.YCODCLI        AS partner_code,
            c.YNOMCLI        AS razao_social,
            c.YFANCLI        AS fantasia,
            c.YCGCCPF        AS cnpj,
            c.YCIDCLI        AS cidade,
            c.YESTCLI        AS uf,
            c.YDATEXC        AS data_exclusao_cliente,
            c.YTIPCLI        AS tipo_cli
        FROM [CLIENTES OU FORNECEDORES] c
        JOIN #nomes_busca nb
          ON c.YNOMCLI LIKE '%' + nb.nome + '%'
          OR c.YFANCLI LIKE '%' + nb.nome + '%'
          OR nb.nome   LIKE '%' + RTRIM(c.YNOMCLI) + '%'
        WHERE c.YTIPCLI = 'C'
        ORDER BY nb.nome, c.YCODCLI
    """)
    cols = [d[0] for d in cur.description]
    q1 = pd.DataFrame.from_records(cur.fetchall(), columns=cols)
    q1['partner_code'] = q1['partner_code'].astype('Int64')
    achados = set(q1['nome_planilha'])
    sem_match = [n for n in nomes if n not in achados]
    print(f'    Q1: {len(q1)} matches; {len(achados)} clientes resolvidos; {len(sem_match)} sem match')

    if sem_match:
        print('    SEM match (até 10):')
        for n in sem_match[:10]:
            print(f'      - {n}')

    if q1.empty:
        print('\n*** Nenhum cliente resolvido. Encerrando antes de Q2/Q3. ***')
        sys.exit(0)

    # ── Q2: pedidos no período
    codes = sorted(set(int(c) for c in q1['partner_code'].dropna()))
    codes_sql = ','.join(str(c) for c in codes)
    print(f'\n[Q2] buscando pedidos em [COMPRAS E VENDAS] para {len(codes)} partner_codes...')
    cur.execute(f"""
        SELECT
            cv.YCODCLI                    AS partner_code,
            cv.YNUMERO                    AS pedido,
            cv.YDATPED                    AS data_pedido,
            cv.YDATNOT                    AS data_nota,
            cv.YNUMNOT                    AS numero_nota,
            cv.YSERNOT                    AS serie_nota,
            cv.YCODNAT                    AS cod_natureza,
            n.YNOMNAT                     AS desc_natureza,
            n.YFINNAT                     AS flag_financeiro,
            n.YESTNAT                     AS flag_estoque,
            n.YDEVNAT                     AS flag_devolucao,
            cv.YSTATUS                    AS status,
            cv.YCONFER                    AS reconcil_flag,
            cv.YDATEXC                    AS data_exclusao_pedido,
            cv.YCODVEN                    AS canal_code,
            cv.YCODVEN2                   AS vendedor_code,
            cv.YVALTOT                    AS valor_total
        FROM [COMPRAS E VENDAS] cv
        LEFT JOIN [NATUREZAS DE OPERAÇÕES] n ON n.YCODNAT = cv.YCODNAT
        WHERE cv.YTIPOPE = 'S'
          AND cv.YDATPED BETWEEN '2025-04-01' AND '2026-04-30'
          AND cv.YCODCLI IN ({codes_sql})
        ORDER BY cv.YCODCLI, cv.YDATPED
    """)
    cols = [d[0] for d in cur.description]
    q2 = pd.DataFrame.from_records(cur.fetchall(), columns=cols)
    q2['partner_code'] = q2['partner_code'].astype('Int64')
    print(f'    Q2: {len(q2)} pedidos no período')
    if not q2.empty:
        ativos = q2[q2['data_exclusao_pedido'].isna()]
        print(f'    -> {len(ativos)} pedidos ATIVOS (YDATEXC NULL); {len(q2) - len(ativos)} excluídos')
        print(f'    -> faturamento ativo TODAS naturezas: R$ {ativos["valor_total"].sum():,.2f}')

    # ── Q3: títulos financeiros em PAGAR E RECEBER
    print(f'\n[Q3] buscando títulos em [PAGAR E RECEBER]...')
    cur.execute(f"""
        SELECT
            pr.YCODCLI         AS partner_code,
            pr.YNUMPED         AS pedido,
            pr.YNUMERO         AS titulo,
            pr.YDOCUME         AS documento,
            pr.YDATEMI         AS data_emissao,
            pr.YDATVEN         AS data_vencimento,
            pr.YDATPAG         AS data_pagamento,
            pr.YVALDOC         AS valor_documento,
            pr.YVALLIQ         AS valor_liquido,
            pr.YVALPAG         AS valor_pago,
            pr.YDATEXC         AS data_exclusao_titulo,
            pr.YNUMNFE         AS num_nfe,
            pr.YDATNFE         AS data_nfe
        FROM [PAGAR E RECEBER] pr
        WHERE pr.YCODCLI IN ({codes_sql})
          AND pr.YDATEMI BETWEEN '2025-04-01' AND '2026-04-30'
        ORDER BY pr.YCODCLI, pr.YDATEMI
    """)
    cols = [d[0] for d in cur.description]
    q3 = pd.DataFrame.from_records(cur.fetchall(), columns=cols)
    q3['partner_code'] = q3['partner_code'].astype('Int64')
    print(f'    Q3: {len(q3)} títulos no período')
    if not q3.empty:
        ativos = q3[q3['data_exclusao_titulo'].isna()]
        print(f'    -> {len(ativos)} títulos ATIVOS')
        print(f'    -> soma valor_documento ativos:  R$ {ativos["valor_documento"].sum():,.2f}')
        print(f'    -> soma valor_pago ativos:       R$ {ativos["valor_pago"].sum():,.2f}')

    cur.close()


# ── 3. Sumário cruzado por cliente ────────────────────────────────────────────
# Soma pedidos ativos por partner_code
sum_q2 = (q2[q2['data_exclusao_pedido'].isna()]
          .groupby('partner_code', as_index=False)
          .agg(n_pedidos=('pedido', 'count'),
               fat_compras_vendas=('valor_total', 'sum')))

sum_q3 = (q3[q3['data_exclusao_titulo'].isna()]
          .groupby('partner_code', as_index=False)
          .agg(n_titulos=('titulo', 'count'),
               fat_pagar_receber=('valor_documento', 'sum'),
               fat_pago=('valor_pago', 'sum')))

sumario = (q1[['nome_planilha', 'partner_code', 'razao_social', 'fantasia',
               'cnpj', 'cidade', 'uf', 'data_exclusao_cliente']]
           .drop_duplicates('partner_code')
           .merge(sum_q2, on='partner_code', how='left')
           .merge(sum_q3, on='partner_code', how='left'))

# Junta com o que o Alves disse (faturamento da planilha)
plan_sub = faltantes[['ID - CLIENTE', 'Valor']].rename(
    columns={'ID - CLIENTE': 'nome_planilha', 'Valor': 'fat_planilha_alves'})
sumario = sumario.merge(plan_sub, on='nome_planilha', how='left')

# ── 4. Excel final ────────────────────────────────────────────────────────────
out = r'C:\Users\gusta\Downloads\hospitalar_82_diagnostico_ERP.xlsx'
with pd.ExcelWriter(out) as w:
    sumario.to_excel(w, sheet_name='0_sumario_por_cliente', index=False)
    q1.to_excel(w, sheet_name='1_clientes_localizados', index=False)
    q2.to_excel(w, sheet_name='2_pedidos_compras_vendas', index=False)
    q3.to_excel(w, sheet_name='3_titulos_pagar_receber', index=False)
    pd.DataFrame({'nome_planilha': sem_match}).to_excel(w, sheet_name='4_sem_match_no_ERP', index=False)
print(f'\n>>> Excel completo: {out}')

# ── 5. Total agregado ─────────────────────────────────────────────────────────
print('\n' + '=' * 80)
print('RESUMO DOS 82 FALTANTES')
print('=' * 80)
print(f'Resolvidos no [CLIENTES OU FORNECEDORES]: {sumario["partner_code"].nunique()}/{len(nomes)}')
print(f'Sem match no ERP:                          {len(sem_match)}/{len(nomes)}')
print()
print(f'Pedidos ATIVOS em [COMPRAS E VENDAS]:      {sum_q2["n_pedidos"].sum() if not sum_q2.empty else 0}')
print(f'Faturamento ATIVO [COMPRAS E VENDAS]:      R$ {sum_q2["fat_compras_vendas"].sum() if not sum_q2.empty else 0:,.2f}')
print()
print(f'Títulos ATIVOS em [PAGAR E RECEBER]:       {sum_q3["n_titulos"].sum() if not sum_q3.empty else 0}')
print(f'Soma valor_doc títulos ativos:             R$ {sum_q3["fat_pagar_receber"].sum() if not sum_q3.empty else 0:,.2f}')
print(f'Soma valor_pago títulos ativos:            R$ {sum_q3["fat_pago"].sum() if not sum_q3.empty else 0:,.2f}')
print()
print(f'Faturamento que o Alves contou (planilha): R$ {plan_sub["fat_planilha_alves"].sum():,.2f}')
