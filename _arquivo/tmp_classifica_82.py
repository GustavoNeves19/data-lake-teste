"""
Para cada um dos 82 clientes faltantes, classificar EM QUAL BUCKET ele se encaixa:
  A. Cliente excluído no ERP (YDATEXC NOT NULL em CLIENTES OU FORNECEDORES)
  B. Cliente ativo no ERP MAS sem pedido no período RFV (apenas histórico antigo)
  C. Tem pedido(s) no período — qual o vendedor (YCODVEN2)?
     E está/não está na carteira BQ — em qual rfv_familia?
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


# ── 1. Carregar 82 faltantes ──────────────────────────────────────────────────
xlsx = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026.xlsx'
plan = pd.read_excel(xlsx, sheet_name='Sem fórmula Geral')
plan['nome_norm'] = plan['ID - CLIENTE'].apply(norm)

bq = bigquery.Client(project='sapient-metrics-492914-m7', location='us-east1')
cart = bq.query("""
SELECT partner_code, partner_name, rfv_familia, salesperson_name, is_active
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
""").to_dataframe()
cart['nome_norm'] = cart['partner_name'].apply(norm)
cart_hosp_ativo_nomes = set(cart[(cart['rfv_familia']=='HOSPITALAR') & (cart['is_active']==True)]['nome_norm'])

faltantes = plan[~plan['nome_norm'].isin(cart_hosp_ativo_nomes)].copy()
nomes = faltantes['ID - CLIENTE'].dropna().tolist()
faltantes_map = {norm(n): n for n in nomes}
print(f'82 faltantes a classificar: {len(nomes)}')


# ── 2. Q1 enxuto no SSM — só YCODCLI + YDATEXC + nome + cnpj ──────────────────
with SQLServerExtractor() as ext:
    cur = ext._conn.cursor()
    cur.execute("IF OBJECT_ID('tempdb..#nomes_busca') IS NOT NULL DROP TABLE #nomes_busca")
    cur.execute("CREATE TABLE #nomes_busca (nome NVARCHAR(255))")
    cur.fast_executemany = True
    cur.executemany("INSERT INTO #nomes_busca (nome) VALUES (?)", [(n,) for n in nomes])
    ext._conn.commit()

    cur.execute("""
        SELECT DISTINCT
            nb.nome    AS nome_planilha,
            c.YCODCLI  AS partner_code,
            c.YNOMCLI  AS razao,
            c.YCGCCPF  AS cnpj,
            c.YCIDCLI  AS cidade,
            c.YESTCLI  AS uf,
            c.YDATEXC  AS data_exclusao
        FROM [CLIENTES OU FORNECEDORES] c
        JOIN #nomes_busca nb
          ON c.YNOMCLI LIKE '%' + nb.nome + '%'
          OR c.YFANCLI LIKE '%' + nb.nome + '%'
          OR nb.nome   LIKE '%' + RTRIM(c.YNOMCLI) + '%'
        WHERE c.YTIPCLI = 'C'
    """)
    cols = [d[0] for d in cur.description]
    q1 = pd.DataFrame.from_records(cur.fetchall(), columns=cols)
    q1['partner_code'] = q1['partner_code'].astype('Int64')
    print(f'Q1 matches (só clientes): {len(q1)} para {q1["nome_planilha"].nunique()} nomes')

    # ── 3. Q2 enxuto: vendedor e valor por pedido ──────────────────────────────
    codes = sorted(set(int(c) for c in q1['partner_code'].dropna()))
    codes_sql = ','.join(str(c) for c in codes)
    cur.execute(f"""
        SELECT
            cv.YCODCLI  AS partner_code,
            cv.YNUMERO  AS pedido,
            cv.YDATPED  AS data_pedido,
            cv.YDATEXC  AS data_excl_pedido,
            cv.YCODVEN2 AS vendedor_code,
            cv.YCODNAT  AS cod_nat,
            n.YFINNAT   AS flag_fin,
            cv.YVALTOT  AS valor
        FROM [COMPRAS E VENDAS] cv
        LEFT JOIN [NATUREZAS DE OPERAÇÕES] n ON n.YCODNAT = cv.YCODNAT
        WHERE cv.YTIPOPE = 'S'
          AND cv.YDATPED BETWEEN '2025-04-01' AND '2026-04-30'
          AND cv.YCODCLI IN ({codes_sql})
    """)
    cols = [d[0] for d in cur.description]
    q2 = pd.DataFrame.from_records(cur.fetchall(), columns=cols)
    q2['partner_code'] = q2['partner_code'].astype('Int64')

    # ── 4. Atendentes — nome do vendedor ────────────────────────────────────────
    cur.execute("""
        SELECT YCODVEN AS vendedor_code, YNOMVEN AS vendedor_nome
        FROM [ATENDENTES]
    """)
    atend = pd.DataFrame.from_records(cur.fetchall(),
                                      columns=['vendedor_code','vendedor_nome'])
    cur.close()


# ── 5. Para cada nome da planilha, pegar o MELHOR partner_code (com pedido) ────
# Estratégia: se múltiplos partner_codes pelo LIKE → preferir o que TEM pedido em Q2
q2_codes_com_pedido = set(q2[q2['data_excl_pedido'].isna()]['partner_code'].dropna().astype(int))

def melhor_match(grp):
    """Retorna 1 linha: o partner_code com mais pedidos no período (ou o primeiro)."""
    # contagem de pedidos ativos por partner_code dentro do grupo
    candidatos = grp.copy()
    candidatos['has_order'] = candidatos['partner_code'].isin(q2_codes_com_pedido)
    candidatos = candidatos.sort_values('has_order', ascending=False)
    return candidatos.iloc[0]

best = q1.groupby('nome_planilha', as_index=False, group_keys=False).apply(melhor_match, include_groups=True)
best = best.reset_index(drop=True)
print(f'Best-match por nome: {len(best)} linhas')

# ── 6. Vendedor preferencial por partner_code (vendedor com mais pedidos do cliente)
vend_por_cli = (q2[q2['data_excl_pedido'].isna()]
                .groupby(['partner_code','vendedor_code'])
                .agg(n_pedidos=('pedido','count'), valor=('valor','sum'))
                .reset_index()
                .sort_values(['partner_code','n_pedidos'], ascending=[True, False]))
vend_top = vend_por_cli.drop_duplicates('partner_code', keep='first')[['partner_code','vendedor_code']]
vend_top = vend_top.merge(atend, on='vendedor_code', how='left')

# ── 7. Cruzar com carteira BQ (todas as famílias) por partner_code ────────────
cart['partner_code'] = cart['partner_code'].astype('Int64')
cart_lookup = cart.drop_duplicates('partner_code')[['partner_code','rfv_familia','salesperson_name','is_active']]

# ── 8. Agregação dos pedidos por cliente (faturamento <>N e =N) ───────────────
ativos = q2[q2['data_excl_pedido'].isna()]
agg_fat = ativos.groupby('partner_code').agg(
    n_pedidos=('pedido','count'),
    fat_total=('valor','sum'),
).reset_index()
agg_neq_n = (ativos[ativos['flag_fin'] != 'N']
             .groupby('partner_code')['valor'].sum().reset_index()
             .rename(columns={'valor':'fat_neq_n'}))
agg_eq_n  = (ativos[ativos['flag_fin'] == 'N']
             .groupby('partner_code')['valor'].sum().reset_index()
             .rename(columns={'valor':'fat_eq_n'}))

base = (best
        .merge(vend_top, on='partner_code', how='left')
        .merge(cart_lookup, on='partner_code', how='left', suffixes=('','_cart'))
        .merge(agg_fat, on='partner_code', how='left')
        .merge(agg_neq_n, on='partner_code', how='left')
        .merge(agg_eq_n, on='partner_code', how='left')
        .merge(faltantes[['ID - CLIENTE','Valor','Classificação 2']]
                  .rename(columns={'ID - CLIENTE':'nome_planilha',
                                   'Valor':'fat_alves',
                                   'Classificação 2':'segmento_alves'}),
               on='nome_planilha', how='left'))

base[['n_pedidos','fat_total','fat_neq_n','fat_eq_n']] = base[['n_pedidos','fat_total','fat_neq_n','fat_eq_n']].fillna(0)

# ── 9. Classificar em bucket ──────────────────────────────────────────────────
def bucket(r):
    if pd.notna(r['data_exclusao']):
        return 'A. Cliente EXCLUIDO no ERP'
    if r['n_pedidos'] == 0:
        return 'B. Sem pedido no período (cliente antigo ou fantasma)'
    fam = r.get('rfv_familia')
    if pd.isna(fam):
        return 'C. Tem pedido — NÃO está na carteira BQ'
    if r.get('is_active') == False:
        return f'D. Tem pedido — carteira inativa ({fam})'
    if fam != 'HOSPITALAR':
        return f'E. Tem pedido — carteira ATIVA em {fam} (não em HOSPITALAR)'
    return 'F. Tem pedido — está em HOSPITALAR-ativo (deveria ter casado, falha de nome)'

base['bucket'] = base.apply(bucket, axis=1)

# ── 10. Resumo por bucket ─────────────────────────────────────────────────────
print('\n' + '=' * 100)
print('CLASSIFICAÇÃO DOS 82 CLIENTES FALTANTES')
print('=' * 100)
res = (base.groupby('bucket')
        .agg(n_clientes=('nome_planilha','count'),
             fat_alves=('fat_alves','sum'),
             fat_neq_n=('fat_neq_n','sum'),
             fat_eq_n=('fat_eq_n','sum'),
             fat_total=('fat_total','sum'))
        .reset_index()
        .sort_values('n_clientes', ascending=False))
for _, r in res.iterrows():
    print(f"\n[{r['bucket']}]")
    print(f"  Clientes: {r['n_clientes']}")
    print(f"  Faturamento Alves (planilha): R$ {r['fat_alves']:>14,.2f}")
    print(f"  ERP <> N (gera financeiro):   R$ {r['fat_neq_n']:>14,.2f}")
    print(f"  ERP  = N (substituição/etc):  R$ {r['fat_eq_n']:>14,.2f}")
    print(f"  ERP total (todas naturezas):  R$ {r['fat_total']:>14,.2f}")
print('\n' + '=' * 100)
print(f"TOTAL  Alves: R$ {base['fat_alves'].sum():,.2f} | ERP<>N: R$ {base['fat_neq_n'].sum():,.2f} | ERP=N: R$ {base['fat_eq_n'].sum():,.2f} | ERP total: R$ {base['fat_total'].sum():,.2f}")

# ── 11. Detalhe por vendedor (de quem são esses clientes) ─────────────────────
com_pedido = base[base['n_pedidos'] > 0]
print('\n' + '=' * 100)
print('VENDEDORES envolvidos (clientes que compraram no período)')
print('=' * 100)
vend = (com_pedido.groupby(['vendedor_code','vendedor_nome'], dropna=False)
        .agg(n_clientes=('nome_planilha','count'),
             fat_alves=('fat_alves','sum'),
             fat_erp=('fat_total','sum'))
        .reset_index()
        .sort_values('fat_alves', ascending=False))
for _, r in vend.iterrows():
    nome = r['vendedor_nome'] if pd.notna(r['vendedor_nome']) else '(sem nome)'
    cod = r['vendedor_code'] if pd.notna(r['vendedor_code']) else '(sem code)'
    print(f"  {cod:<6} {nome:<35} {r['n_clientes']:>4} cli   Alves R$ {r['fat_alves']:>12,.2f}   ERP R$ {r['fat_erp']:>12,.2f}")

# ── 12. Salvar Excel ──────────────────────────────────────────────────────────
out = r'C:\Users\gusta\Downloads\hospitalar_82_classificados.xlsx'
with pd.ExcelWriter(out) as w:
    base.to_excel(w, sheet_name='detalhe_82_clientes', index=False)
    res.to_excel(w, sheet_name='resumo_bucket', index=False)
    vend.to_excel(w, sheet_name='resumo_vendedor', index=False)
print(f'\n>>> Excel: {out}')
