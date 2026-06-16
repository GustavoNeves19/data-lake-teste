"""
Query 1 — localizar YCODCLI (partner_code) no NSR_ERP via LIKE pelo nome
para os 82 clientes da planilha Alves que sumiram da carteira BQ HOSPITALAR.
"""
import io, os, sys, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni')

import pandas as pd
from extract.sqlserver import SQLServerExtractor


def norm(s):
    if s is None or pd.isna(s): return ''
    s = str(s).upper().strip()
    s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', s)


# 1. Carrega 82 faltantes
import pyodbc
from google.cloud import bigquery
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

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
print(f'[1/3] Faltantes: {len(nomes)} clientes Hospitalar')

# 2. Descobre primeiro a estrutura da tabela [CLIENTES]
with SQLServerExtractor() as ext:
    cur = ext._conn.cursor()
    cur.execute("""
        SELECT TOP 5 *
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'CLIENTES'
          AND COLUMN_NAME LIKE 'Y%'
        ORDER BY ORDINAL_POSITION
    """)
    print('Exemplo de colunas Y* em [CLIENTES]:')
    for row in cur.fetchall():
        print(f'  {row.COLUMN_NAME} ({row.DATA_TYPE})')

    cur.execute("""
        SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'CLIENTES'
    """)
    print(f'Total colunas [CLIENTES]: {cur.fetchone().n}')

    # 3. Confere colunas que vamos usar
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'CLIENTES'
          AND COLUMN_NAME IN ('YCODCLI','YRAZSOC','YFANTAS','YCNPJCP','YCIDADE','YESTADO','YDATEXC')
    """)
    have = [r.COLUMN_NAME for r in cur.fetchall()]
    print(f'Colunas presentes esperadas: {have}')
    cur.close()

    # 4. Cria tabela temp com os 82 nomes e faz LIKE
    cur = ext._conn.cursor()
    cur.execute("IF OBJECT_ID('tempdb..#nomes_busca') IS NOT NULL DROP TABLE #nomes_busca")
    cur.execute("CREATE TABLE #nomes_busca (nome NVARCHAR(255))")
    cur.fast_executemany = True
    cur.executemany("INSERT INTO #nomes_busca (nome) VALUES (?)", [(n,) for n in nomes])
    ext._conn.commit()
    cur.execute("SELECT COUNT(*) AS n FROM #nomes_busca")
    print(f'#nomes_busca populada com {cur.fetchone().n} nomes')

    # 5. LIKE bilateral
    cur.execute("""
        SELECT DISTINCT
            nb.nome       AS nome_planilha,
            c.YCODCLI     AS partner_code,
            c.YRAZSOC     AS razao_social,
            c.YFANTAS     AS fantasia,
            c.YCNPJCP     AS cnpj,
            c.YCIDADE     AS cidade,
            c.YESTADO     AS uf,
            c.YDATEXC     AS data_exclusao
        FROM [CLIENTES] c
        JOIN #nomes_busca nb
          ON c.YRAZSOC LIKE '%' + nb.nome + '%'
          OR c.YFANTAS LIKE '%' + nb.nome + '%'
          OR nb.nome LIKE '%' + c.YRAZSOC + '%'
        ORDER BY nb.nome, c.YCODCLI
    """)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    df = pd.DataFrame.from_records(rows, columns=cols)
    print(f'\n>>> Query 1 — {len(df)} match(es) encontrados para {df["nome_planilha"].nunique()} de {len(nomes)} clientes')

    # quantos resolveram, quantos não
    achados = set(df['nome_planilha'])
    nao_achados = [n for n in nomes if n not in achados]
    print(f'    Resolvidos: {len(achados)}')
    print(f'    SEM match no [CLIENTES]: {len(nao_achados)}')
    if nao_achados:
        print('    Exemplos (até 10):')
        for n in nao_achados[:10]:
            print(f'      - {n}')

out_q1 = r'C:\Users\gusta\Downloads\ssm_q1_clientes_localizados.xlsx'
with pd.ExcelWriter(out_q1) as w:
    df.to_excel(w, 'matches', index=False)
    pd.DataFrame({'nome_planilha': nao_achados}).to_excel(w, 'sem_match', index=False)
print(f'\n>>> Salvo: {out_q1}')

# Lista de partner_code única (para próxima query)
codes = sorted({int(c) for c in df['partner_code'].dropna().tolist()})
print(f'>>> partner_codes únicos: {len(codes)}')
with open(r'C:\Users\gusta\OneDrive\Documentos\Data-Lake\data_lake_nevoni\tmp_ssm_codes.txt', 'w') as f:
    f.write(','.join(str(c) for c in codes))
