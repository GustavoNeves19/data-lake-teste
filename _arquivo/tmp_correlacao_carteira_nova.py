"""CORRELAÇÃO: carteira atual (BQ) × nova carteira do Alves (Inside Sales + Farmácia)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 60)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# 1) NOVA CARTEIRA — Inside Sales (Hospitalar + SAC)
print('Lendo Inside Sales...')
df_is = pd.read_excel(
    r'C:\Users\gusta\Downloads\Carteira de Clientes - Inside Sales (Atualizado).xlsx',
    sheet_name='Planilha1', header=14
)
df_is = df_is[['ID CRM','ID ERP','CNPJ','Razão Social','Vendedor Responsável']].copy()
df_is.columns = ['id_crm','id_erp','cnpj','razao','vendedor_nova']
# Vendedor D vazio → Kauan Ramos (confirmação WhatsApp Alves)
df_is['vendedor_nova'] = df_is['vendedor_nova'].fillna(0).astype(str).replace({'0':'Kauan Ramos'})
df_is['fonte_planilha'] = 'Inside Sales (Hosp+SAC)'

# 2) NOVA CARTEIRA — Farmers Farmácia (Cauã Ribeiro)
print('Lendo Farmácia...')
df_fa = pd.read_excel(
    r'C:\Users\gusta\Downloads\Farmers Farmacias (version 1)(Recuperado Automaticamente) (3) (1).xlsx',
    sheet_name='Carteira Farmer Farm. (Ribeiro)', header=3
)
# Renomeia
df_fa = df_fa.rename(columns={c: str(c).strip() for c in df_fa.columns})
df_fa = df_fa[['ID ERP','CNPJ','Razão Social']].copy()
df_fa.columns = ['id_erp','cnpj','razao']
df_fa['id_crm'] = None
df_fa['vendedor_nova'] = 'Cauã Ribeiro'
df_fa['fonte_planilha'] = 'Farmers Farmácia'

# Junta
df_nova = pd.concat([df_is, df_fa], ignore_index=True)
df_nova = df_nova[df_nova['id_erp'].notna()].copy()
df_nova['id_erp'] = pd.to_numeric(df_nova['id_erp'], errors='coerce').astype('Int64')
df_nova = df_nova.dropna(subset=['id_erp']).copy()

print(f'\nTotal NOVA carteira (com ID ERP): {len(df_nova)}')
print(df_nova['vendedor_nova'].value_counts().to_string())
print()
print('Por fonte:')
print(df_nova['fonte_planilha'].value_counts().to_string())

# 3) CARTEIRA ATUAL no BQ
print('\nLendo carteira atual do BQ...')
df_atual = c.query("""
SELECT partner_code, partner_name, rfv_familia, salesperson_name, is_active
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
WHERE is_active = TRUE
""").to_dataframe()
df_atual['id_erp'] = df_atual['partner_code'].astype('Int64')
print(f'Carteira atual ativa: {len(df_atual)}')

# 4) MERGE — match por ID ERP
print('\n' + '=' * 90)
print('MATCH CARTEIRA ATUAL × NOVA (por ID ERP)')
print('=' * 90)

# Para cada partner_code da nova, agrega vendedores (pode aparecer 2x se estiver Hosp+SAC e Farma)
nova_agg = df_nova.groupby('id_erp').agg(
    vendedor_nova=('vendedor_nova', lambda x: ' | '.join(sorted(set(x)))),
    fontes=('fonte_planilha', lambda x: ' | '.join(sorted(set(x)))),
).reset_index()

merge = df_atual.merge(nova_agg, on='id_erp', how='outer', indicator=True)

print(f'\nClientes da carteira ATUAL: {len(df_atual)}')
print(f'Clientes da nova carteira (unique IDs): {len(nova_agg)}')
print()
print('Distribuicao do match:')
print(merge['_merge'].value_counts().to_string())
print()
print('  left_only  = clientes da carteira ATUAL que NAO estao na nova planilha (= "cliente novo"? ou inativo?)')
print('  right_only = clientes da NOVA planilha que ainda nao estao na carteira atual')
print('  both       = batem perfeitamente')

# 5) Comparativo de vendedores (only "both")
print('\n' + '=' * 90)
print('MUDANCAS DE VENDEDOR (clientes presentes nas duas)')
print('=' * 90)
match = merge[merge['_merge']=='both'].copy()
match['match_vendedor'] = match.apply(lambda r:
    'mesmo' if any(v.lower() in str(r['vendedor_nova']).lower() or str(r['salesperson_name']).lower() in v.lower()
                   for v in str(r['vendedor_nova']).split(' | '))
    else 'MUDA', axis=1)
print(f'Total matches: {len(match)}')
print()
print('Status:')
print(match['match_vendedor'].value_counts().to_string())

print('\n=== Por vendedor ATUAL → quem fica como vendedor NOVO ===')
ct = pd.crosstab(match['salesperson_name'].fillna('NULL'), match['vendedor_nova'].fillna('NULL'), margins=True, margins_name='TOTAL')
print(ct.to_string())

# 6) "left_only" = carteira atual com clientes que NAO estao na nova planilha
print('\n' + '=' * 90)
print('CARTEIRA ATUAL × NAO ESTA NA NOVA PLANILHA (potenciais "cliente novo" ou inativos)')
print('=' * 90)
left = merge[merge['_merge']=='left_only'].copy()
print(f'Total: {len(left)} clientes')
print('\nPor familia da carteira atual:')
print(left.groupby('rfv_familia').size().to_string())
print('\nPor vendedor atual:')
print(left['salesperson_name'].fillna('NULL').value_counts().to_string())

# 7) "right_only" = nova planilha tem clientes que carteira atual NAO tem
print('\n' + '=' * 90)
print('NOVA PLANILHA × NAO ESTA NA CARTEIRA ATUAL (faltam adicionar)')
print('=' * 90)
right = merge[merge['_merge']=='right_only'].copy()
print(f'Total: {len(right)} clientes')
print('\nPor vendedor da nova planilha:')
print(right['vendedor_nova'].fillna('NULL').value_counts().to_string())
print('\nPor fonte:')
print(right['fontes'].fillna('NULL').value_counts().to_string())

# 8) Resumo final
print('\n' + '=' * 90)
print('RESUMO EXECUTIVO PARA O ALVES')
print('=' * 90)
print(f"""
CARTEIRA ATUAL (BQ):   {len(df_atual):>5} clientes ativos
NOVA PLANILHA TOTAL:   {len(nova_agg):>5} clientes (Hosp+SAC: {df_is['id_erp'].dropna().nunique()}, Farmácia: {df_fa['id_erp'].dropna().nunique()})

MATCH (ID ERP bate):                       {len(match):>5}  ({len(match)/len(df_atual)*100:.1f}% da carteira atual)
SO NA CARTEIRA ATUAL (nao na nova):        {len(left):>5}  → considerar como "Cliente Novo" ou inativar
SO NA NOVA PLANILHA (faltam na carteira):  {len(right):>5}  → adicionar na carteira (com vendedor da nova)

CONFLITOS DE VENDEDOR (cliente em ambos com nomes diferentes):
""")
muda = match[match['match_vendedor']=='MUDA']
print(f'  {len(muda)} clientes precisam atualizar vendedor (carteira atual ≠ nova planilha)')

# Salva CSV detalhado
out_left = r'C:\Users\gusta\Downloads\carteira_so_atual_nao_na_nova.csv'
out_right = r'C:\Users\gusta\Downloads\carteira_nova_falta_adicionar.csv'
out_muda = r'C:\Users\gusta\Downloads\carteira_conflito_vendedor.csv'
left[['id_erp','partner_name','rfv_familia','salesperson_name']].to_csv(out_left, index=False, encoding='utf-8-sig')
right[['id_erp','vendedor_nova','fontes']].to_csv(out_right, index=False, encoding='utf-8-sig')
muda[['id_erp','partner_name','rfv_familia','salesperson_name','vendedor_nova']].to_csv(out_muda, index=False, encoding='utf-8-sig')
print(f'\nCSVs salvos:')
print(f'  {out_left}')
print(f'  {out_right}')
print(f'  {out_muda}')
