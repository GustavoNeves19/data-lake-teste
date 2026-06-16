"""Investigação profunda do gap HOSPITALAR (Excel Alves 786 vs Sistema 714)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.max_colwidth', 60)
pd.set_option('display.width', 250)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# 1) Excel HOSPITALAR
path = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026 (1).xlsx'
df_e = pd.read_excel(path, sheet_name='Sem fórmula Geral')
df_e['k'] = df_e['ID - CLIENTE'].astype(str).str.upper().str.strip()
excel_names = set(df_e['k'].tolist())
print(f'Excel HOSPITALAR: {len(excel_names)} clientes')

# 2) Sistema HOSPITALAR (com data ref 30/04/2026)
df_s = client.query("""
SELECT DISTINCT partner_name
FROM `sapient-metrics-492914-m7.silver_comercial.silver_com_rfv_score`
WHERE rfv_familia = 'HOSPITALAR' AND DATE(data_referencia) = '2026-04-30'
""").to_dataframe()
df_s['k'] = df_s['partner_name'].str.upper().str.strip()
sis_names = set(df_s['k'].tolist())
print(f'Sistema HOSPITALAR (30/04/26): {len(sis_names)} clientes')

# 3) Quem está no Excel mas não no sistema
falta = excel_names - sis_names
extra = sis_names - excel_names
print(f'\nSó no Excel (faltando no sistema): {len(falta)}')
print(f'Só no sistema (extras): {len(extra)}')

# 4) Investigar cada um dos faltantes no ERP
nomes_falta = sorted(falta)
df_falta_excel = df_e[df_e['k'].isin(falta)][['k','ID - CLIENTE','Frequência 1','Valor']].copy()
df_falta_excel.columns = ['k','nome_excel','freq_excel','valor_excel']

# 5) Buscar no ERP TODOS os partner_codes com esses nomes (exato ou variante)
ex = SQLServerExtractor()
ex.connect()

# Faz busca em batches
print(f'\nInvestigando {len(nomes_falta)} clientes faltantes no ERP...')
resultados = []
for nome in nomes_falta:
    # Escape de aspas
    nome_sql = nome.replace("'", "''")
    df_erp = pd.read_sql(f"""
    SELECT
        YCODCLI                                                       AS partner_code,
        YNOMCLI                                                       AS nome_erp,
        CASE WHEN YDATEXC IS NULL THEN 1 ELSE 0 END                  AS ativo_erp,
        YDATEXC                                                       AS excluido_em
    FROM [CLIENTES OU FORNECEDORES]
    WHERE UPPER(LTRIM(RTRIM(YNOMCLI))) = '{nome_sql}'
    """, ex._conn)
    if df_erp.empty:
        resultados.append({'nome': nome, 'erp_partner_codes': 'NAO EXISTE NO ERP', 'erp_ativos': 0, 'erp_excluidos': 0})
    else:
        ativos = int(df_erp['ativo_erp'].sum())
        excluidos = len(df_erp) - ativos
        codes = ','.join(df_erp['partner_code'].astype(str).tolist())
        resultados.append({'nome': nome, 'erp_partner_codes': codes, 'erp_ativos': ativos, 'erp_excluidos': excluidos})

df_invest = pd.DataFrame(resultados)
df_invest = df_invest.merge(df_falta_excel, left_on='nome', right_on='k', how='left')[
    ['nome','freq_excel','valor_excel','erp_partner_codes','erp_ativos','erp_excluidos']
]

print(f'\n=== Categorização dos {len(df_invest)} faltantes ===')
df_invest['categoria'] = df_invest.apply(lambda r:
    'A) Nao existe no ERP' if r['erp_partner_codes'] == 'NAO EXISTE NO ERP'
    else ('B) Todos partner_codes excluidos' if r['erp_ativos'] == 0
          else 'C) Tem partner_code ATIVO no ERP'), axis=1)
print(df_invest['categoria'].value_counts().to_string())

# 6) Para categoria C (existe ATIVO no ERP), check: está na carteira?
print(f'\n=== Categoria C: faltantes com partner_code ATIVO no ERP ===')
categoria_c = df_invest[df_invest['categoria'] == 'C) Tem partner_code ATIVO no ERP']
print(f'{len(categoria_c)} clientes nessa categoria')
print()
print('Esses sao os mais importantes — existem no ERP mas o sistema nao captura. Por que?')

# Cruzar com carteira
df_cart = client.query("""
SELECT partner_code, partner_name, rfv_familia, is_active
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
""").to_dataframe()
cart_codes_ativos = set(df_cart[df_cart['is_active']==True]['partner_code'].astype(str).tolist())
cart_codes_inativos = set(df_cart[df_cart['is_active']==False]['partner_code'].astype(str).tolist())

def categoriza_carteira(codes_str):
    if codes_str == 'NAO EXISTE NO ERP':
        return 'N/A'
    codes = codes_str.split(',')
    em_cart_ativa = [c for c in codes if c in cart_codes_ativos]
    em_cart_inativa = [c for c in codes if c in cart_codes_inativos]
    fora_da_cart = [c for c in codes if c not in cart_codes_ativos and c not in cart_codes_inativos]
    if em_cart_ativa:
        return f'C1) Ja na carteira ATIVA ({len(em_cart_ativa)} codes)'
    if em_cart_inativa:
        return f'C2) Na carteira INATIVA ({len(em_cart_inativa)} codes)'
    return f'C3) FORA da carteira ({len(fora_da_cart)} codes)'

categoria_c = categoria_c.copy()
categoria_c['situacao_carteira'] = categoria_c['erp_partner_codes'].apply(categoriza_carteira)
print(categoria_c['situacao_carteira'].value_counts().to_string())

print()
print('=== Amostra (top 20 por valor no Excel) ===')
print(categoria_c.sort_values('valor_excel', ascending=False).head(20).to_string(index=False))

# Salva CSV pra investigação
out = r'C:\Users\gusta\Downloads\investiga_gap_hospitalar.csv'
df_invest.to_csv(out, index=False, encoding='utf-8-sig')
print(f'\nCSV completo salvo: {out}')
