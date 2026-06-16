"""
Gera o pacote final para investigação no SSM:
  - lista dos 82 clientes Hospitalar faltantes (nome conforme planilha Alves)
  - query SSM com #temp populada por todos os nomes para LIKE direto no NSR_ERP
  - planilha com candidatos encontrados via LIKE no dim_partner BQ (pré-pesquisa)
"""
import io, os, sys, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', r'C:\teste\sapient-metrics.json')

import pandas as pd
from google.cloud import bigquery

PROJ = 'sapient-metrics-492914-m7'
client = bigquery.Client(project=PROJ, location='us-east1')

def norm(s):
    if s is None or pd.isna(s): return ''
    s = str(s).upper().strip()
    s = ''.join(ch for ch in unicodedata.normalize('NFD', s) if unicodedata.category(ch) != 'Mn')
    return re.sub(r'\s+', ' ', s)

# 1. Planilha Alves
xlsx = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026.xlsx'
plan = pd.read_excel(xlsx, sheet_name='Sem fórmula Geral')
plan['nome_norm'] = plan['ID - CLIENTE'].apply(norm)

# 2. Carteira HOSPITALAR ativa
cart = client.query(f"""
SELECT partner_code, partner_name
FROM `{PROJ}.silver_comercial.param_com_rfv_carteira`
WHERE is_active = TRUE AND rfv_familia = 'HOSPITALAR'
""").to_dataframe()
cart['nome_norm'] = cart['partner_name'].apply(norm)
nomes_cart = set(cart['nome_norm'])

faltantes = plan[~plan['nome_norm'].isin(nomes_cart)].copy()
print(f'Faltantes: {len(faltantes)}')

# 3. Para cada faltante: pesquisar candidatos no dim_partner usando "primeira palavra significativa"
STOP = {'A','O','AS','OS','DE','DA','DO','DAS','DOS','E','LTDA','ME','EPP','EIRELI',
        'SA','S/A','S.A','S.A.','HOSPITAL','HOSPITALAR','HOSPITALARES','EQUIPAMENTOS',
        'COMERCIO','COM','INDUSTRIA','IND','CIA','&'}

def chave_busca(nome):
    s = norm(nome)
    s = re.sub(r'^\s*[\d\.\-/]+\s+', '', s)  # remove CNPJ prefix
    palavras = [w for w in re.findall(r'\w+', s) if w not in STOP and len(w) >= 3]
    return ' '.join(palavras[:3])  # primeiras 3 palavras significativas

faltantes['chave'] = faltantes['ID - CLIENTE'].apply(chave_busca)

# Carrega dim_partner inteiro
dim = client.query(f"""
SELECT partner_code, partner_name, legal_name, tax_id, city, state, status
FROM `{PROJ}.dm_partners.dim_partner`
""").to_dataframe()
dim['nome_norm'] = dim['partner_name'].apply(norm)
dim['legal_norm'] = dim['legal_name'].apply(norm)

# Buscar candidatos
candidatos_rows = []
for _, r in faltantes.iterrows():
    nome_plan = r['ID - CLIENTE']
    chave = r['chave']
    if not chave:
        candidatos_rows.append({'planilha_nome': nome_plan, 'chave_busca': '',
                                'partner_code': None, 'dim_partner_name': '',
                                'dim_legal_name': '', 'tax_id': '', 'city': '', 'state': '', 'status': ''})
        continue
    # busca: dim que contém TODAS as palavras da chave
    palavras = chave.split()
    mask = pd.Series([True] * len(dim))
    for p in palavras:
        m = dim['nome_norm'].str.contains(re.escape(p), na=False) | dim['legal_norm'].str.contains(re.escape(p), na=False)
        mask &= m
    matches = dim[mask].head(5)
    if matches.empty:
        candidatos_rows.append({'planilha_nome': nome_plan, 'chave_busca': chave,
                                'partner_code': None, 'dim_partner_name': '',
                                'dim_legal_name': '', 'tax_id': '', 'city': '', 'state': '', 'status': ''})
    else:
        for _, c in matches.iterrows():
            candidatos_rows.append({
                'planilha_nome': nome_plan, 'chave_busca': chave,
                'partner_code': c['partner_code'],
                'dim_partner_name': c['partner_name'],
                'dim_legal_name':   c['legal_name'],
                'tax_id': c['tax_id'], 'city': c['city'], 'state': c['state'], 'status': c['status'],
            })

df_cand = pd.DataFrame(candidatos_rows)
print(f'Candidatos gerados: {len(df_cand)} linhas para {df_cand["planilha_nome"].nunique()} clientes únicos')
sem_match = df_cand[df_cand['partner_code'].isna()]['planilha_nome'].unique()
print(f'Sem nenhum candidato no dim_partner: {len(sem_match)}')

# 4. Faturamento BQ por partner_code que apareceu como candidato (período RFV-abril, TODAS naturezas)
codes = sorted(int(c) for c in df_cand['partner_code'].dropna().unique())
if codes:
    codes_sql = ','.join(str(c) for c in codes)
    fat = client.query(f"""
    SELECT o.partner_code,
           o.nature_code,
           n.financial_flag,
           n.nature_name,
           COUNT(DISTINCT o.order_number) AS pedidos,
           ROUND(SUM(o.total_amount), 2)  AS faturamento
    FROM `{PROJ}.dm_orders.fact_sales_order` o
    LEFT JOIN `{PROJ}.dm_orders.dim_operation_nature` n ON n.nature_code = o.nature_code
    WHERE o.partner_code IN ({codes_sql})
      AND o.order_status IN (3, 4)
      AND o.order_date >= DATE '2025-04-01'
      AND o.order_date <= DATE '2026-04-30'
    GROUP BY o.partner_code, o.nature_code, n.financial_flag, n.nature_name
    """).to_dataframe()
    print(f'Faturamento (linhas natureza×cliente): {len(fat)}')
    print(f'  Soma TODAS naturezas:  R$ {fat["faturamento"].sum():>14,.2f}')
    print(f'  Soma <> N (conta):     R$ {fat[fat["financial_flag"] != "N"]["faturamento"].sum():>14,.2f}')
    print(f'  Soma  = N (não conta): R$ {fat[fat["financial_flag"] == "N"]["faturamento"].sum():>14,.2f}')
else:
    fat = pd.DataFrame()

# 5. Excel final
out = r'C:\Users\gusta\Downloads\hospitalar_82_faltantes_SSM.xlsx'
with pd.ExcelWriter(out) as w:
    faltantes[['ID - CLIENTE','Frequência 1','Data última compra','Recência em dias',
               'Classificação 2','Valor','chave']].rename(columns={
                   'ID - CLIENTE':'nome_planilha_alves',
                   'Frequência 1':'freq_alves',
                   'Data última compra':'ultima_compra_alves',
                   'Recência em dias':'recencia_alves',
                   'Classificação 2':'segmento_alves',
                   'Valor':'faturamento_alves',
                   'chave':'chave_busca'
               }).to_excel(w, '1_lista_82_faltantes', index=False)

    df_cand.to_excel(w, '2_candidatos_dim_partner', index=False)
    if not fat.empty:
        fat.to_excel(w, '3_faturamento_bq_por_natureza', index=False)
print(f'>>> Excel salvo: {out}')

# 6. Query SSM
nomes_para_sql = faltantes['ID - CLIENTE'].dropna().unique().tolist()
sql_lines = []
sql_lines.append("-- ============================================================")
sql_lines.append("-- DIAGNÓSTICO HOSPITALAR FALTANTES (NSR_ERP)")
sql_lines.append("-- Investiga 82 clientes da planilha RFV Hospitalar de abril/2026 que")
sql_lines.append("-- não apareceram na carteira BQ-HOSPITALAR-ATIVA.")
sql_lines.append("-- Janela do RFV: 01/04/2025 a 30/04/2026")
sql_lines.append("-- ============================================================")
sql_lines.append("")
sql_lines.append("IF OBJECT_ID('tempdb..#nomes_busca') IS NOT NULL DROP TABLE #nomes_busca;")
sql_lines.append("CREATE TABLE #nomes_busca (nome NVARCHAR(255));")
sql_lines.append("INSERT INTO #nomes_busca (nome) VALUES")
vals = ",\n".join(f"  ('{n.replace(chr(39), chr(39)+chr(39))}')" for n in nomes_para_sql)
sql_lines.append(vals + ";")
sql_lines.append("")
sql_lines.append("-- 1) Localizar partner_code (YCODCLI) por nome semelhante")
sql_lines.append("SELECT DISTINCT")
sql_lines.append("    c.YCODCLI       AS partner_code,")
sql_lines.append("    c.YRAZSOC       AS razao_social,")
sql_lines.append("    c.YFANTAS       AS nome_fantasia,")
sql_lines.append("    c.YCNPJCP       AS cnpj_cpf,")
sql_lines.append("    c.YCIDADE       AS cidade,")
sql_lines.append("    c.YESTADO       AS uf,")
sql_lines.append("    c.YDATEXC       AS data_exclusao,")
sql_lines.append("    nb.nome         AS nome_planilha_alves")
sql_lines.append("FROM [CLIENTES] c")
sql_lines.append("JOIN #nomes_busca nb")
sql_lines.append("  ON c.YRAZSOC LIKE '%' + nb.nome + '%'")
sql_lines.append("  OR c.YFANTAS LIKE '%' + nb.nome + '%'")
sql_lines.append("  OR nb.nome   LIKE '%' + c.YRAZSOC + '%'")
sql_lines.append("ORDER BY nb.nome, c.YCODCLI;")
sql_lines.append("")
sql_lines.append("-- 2) Pedidos de COMPRAS E VENDAS no período para os clientes encontrados")
sql_lines.append("-- (copiar os YCODCLI da query anterior na lista abaixo)")
sql_lines.append("SELECT")
sql_lines.append("    cv.YCODCLI       AS partner_code,")
sql_lines.append("    cv.YNUMERO       AS pedido,")
sql_lines.append("    cv.YDATPED       AS data_pedido,")
sql_lines.append("    cv.YDATNOT       AS data_nota,")
sql_lines.append("    cv.YNUMNOT       AS numero_nota,")
sql_lines.append("    cv.YCODNAT       AS cod_natureza,")
sql_lines.append("    n.YDESNAT        AS descricao_natureza,")
sql_lines.append("    n.YFLG__1        AS financial_flag,")
sql_lines.append("    cv.YVALTOT       AS valor_total,")
sql_lines.append("    cv.YSTATUS       AS status,")
sql_lines.append("    cv.YDATEXC       AS data_exclusao,")
sql_lines.append("    cv.YCODVEN       AS canal_code,")
sql_lines.append("    cv.YCODVEN2      AS vendedor_code")
sql_lines.append("FROM [COMPRAS E VENDAS] cv")
sql_lines.append("LEFT JOIN [NATUREZA DE OPERACAO] n ON n.YCODNAT = cv.YCODNAT")
sql_lines.append("WHERE cv.YTIPOPE = 'S'")
sql_lines.append("  AND cv.YDATEXC IS NULL")
sql_lines.append("  AND cv.YDATPED BETWEEN '2025-04-01' AND '2026-04-30'")
sql_lines.append("  AND cv.YCODCLI IN (/* COLAR partner_code DA QUERY 1 */)")
sql_lines.append("ORDER BY cv.YCODCLI, cv.YDATPED;")
sql_lines.append("")
sql_lines.append("-- 3) Tabela financeira (CONTAS A RECEBER) - confirmar se virou título faturado")
sql_lines.append("--    Substituir [PAGAS E RECEBIDAS] pelo nome real da tabela financeira do NSR_ERP")
sql_lines.append("SELECT")
sql_lines.append("    cr.YCODCLI       AS partner_code,")
sql_lines.append("    cr.YNUMERO       AS pedido_origem,")
sql_lines.append("    cr.YNUMTIT       AS titulo,")
sql_lines.append("    cr.YDATEMI       AS data_emissao,")
sql_lines.append("    cr.YDATVEN       AS data_vencimento,")
sql_lines.append("    cr.YVALTIT       AS valor_titulo,")
sql_lines.append("    cr.YSITUAC       AS situacao,        -- baixado/aberto")
sql_lines.append("    cr.YCODNAT       AS cod_natureza,")
sql_lines.append("    cr.YDATEXC       AS data_exclusao")
sql_lines.append("FROM [CONTAS A RECEBER] cr   -- AJUSTAR nome da tabela")
sql_lines.append("WHERE cr.YDATEXC IS NULL")
sql_lines.append("  AND cr.YDATEMI BETWEEN '2025-04-01' AND '2026-04-30'")
sql_lines.append("  AND cr.YCODCLI IN (/* COLAR partner_code DA QUERY 1 */)")
sql_lines.append("ORDER BY cr.YCODCLI, cr.YDATEMI;")
sql_lines.append("")
sql_lines.append("DROP TABLE #nomes_busca;")

sql_path = r'C:\Users\gusta\Downloads\diagnostico_hospitalar_82_faltantes.sql'
with open(sql_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(sql_lines))
print(f'>>> SQL salvo: {sql_path}')
print(f'    {len(nomes_para_sql)} nomes na #nomes_busca')
