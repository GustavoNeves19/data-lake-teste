"""Regenera carteira_conflito_vendedor.csv com lógica correta + atualiza ZIP."""
import sys, io, zipfile
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 220)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# Re-lê as fontes
df_is = pd.read_excel(
    r'C:\Users\gusta\Downloads\Carteira de Clientes - Inside Sales (Atualizado).xlsx',
    sheet_name='Planilha1', header=14
)[['ID ERP','Razão Social','Vendedor Responsável']].copy()
df_is.columns = ['id_erp','razao','vendedor_nova']
df_is['vendedor_nova'] = df_is['vendedor_nova'].fillna(0).astype(str).replace({'0':'Kauan Ramos'})
df_is['fonte'] = 'Inside Sales'

df_fa = pd.read_excel(
    r'C:\Users\gusta\Downloads\Farmers Farmacias (version 1)(Recuperado Automaticamente) (3) (1).xlsx',
    sheet_name='Carteira Farmer Farm. (Ribeiro)', header=3
)
df_fa = df_fa.rename(columns={c: str(c).strip() for c in df_fa.columns})
df_fa = df_fa[['ID ERP','Razão Social']].copy()
df_fa.columns = ['id_erp','razao']
df_fa['vendedor_nova'] = 'Cauã Ribeiro'
df_fa['fonte'] = 'Farmácia'

df_nova = pd.concat([df_is, df_fa], ignore_index=True)
df_nova['id_erp'] = pd.to_numeric(df_nova['id_erp'], errors='coerce').astype('Int64')
df_nova = df_nova.dropna(subset=['id_erp'])
nova_agg = df_nova.groupby('id_erp').agg(
    vendedor_nova=('vendedor_nova', lambda x: ' | '.join(sorted(set(x)))),
    fontes=('fonte', lambda x: ' | '.join(sorted(set(x)))),
).reset_index()

df_atual = c.query("""
SELECT partner_code AS id_erp, partner_name, rfv_familia, salesperson_name
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_rfv_carteira`
WHERE is_active = TRUE
""").to_dataframe()
df_atual['id_erp'] = df_atual['id_erp'].astype('Int64')

# Match
m = df_atual.merge(nova_agg, on='id_erp', how='inner')

# Mapeamento OFICIAL atual -> novo (apenas renames diretos)
RENAMES_OFICIAIS = {
    'Ramos': 'Kauan Ramos',
    'Ribeiro': 'Cauã Ribeiro',
    'Eduardo': 'Eduardo Marques',
    'Giovanna': 'Geovanna Gomes',
    'Guilherme': 'Guilherme Aquino',
    'Kaua': 'Kauã Rodrigues',
    'Richard': 'Richard Lucas',
}

def diverge(row):
    atual = str(row['salesperson_name'] or '').strip()
    nova = str(row['vendedor_nova'] or '').strip()
    if atual == 'Sem Vendedor':
        return 'GANHA_DONO'
    # Se o nome atual está no rename oficial e bate com o novo, é só rename
    rename_esperado = RENAMES_OFICIAIS.get(atual)
    if rename_esperado and rename_esperado in nova:
        return 'rename_ok'
    # Senão, vendedor mudou de pessoa
    return 'TROCA_VENDEDOR'

m['status'] = m.apply(diverge, axis=1)

print('Distribuição de status:')
print(m['status'].value_counts().to_string())

# Salva o CSV de conflito agora COMPLETO (todos os status visíveis)
out = Path(r'C:\Users\gusta\Downloads\carteira_conflito_vendedor.csv')
m_out = m[['id_erp','partner_name','rfv_familia','salesperson_name','vendedor_nova','status']].copy()
m_out = m_out.rename(columns={
    'salesperson_name': 'vendedor_atual',
})
m_out = m_out.sort_values(['status', 'rfv_familia', 'partner_name'])
m_out.to_csv(out, index=False, encoding='utf-8-sig')
print(f'\nCSV salvo: {out} ({out.stat().st_size:,} bytes)')

# Refaz o ZIP
dl = Path(r'C:\Users\gusta\Downloads')
zip_path = dl / 'carteira_correlacao_25-05-2026.zip'

readme_extra = f"""\

================================================================
DISTRIBUICAO DETALHADA DO MATCH (1.016 clientes)
================================================================

GANHA_DONO       {(m['status']=='GANHA_DONO').sum():>5}  (eram "Sem Vendedor" e agora ganham dono)
rename_ok        {(m['status']=='rename_ok').sum():>5}  (so mudou o nome — ex: Ramos -> Kauan Ramos)
TROCA_VENDEDOR   {(m['status']=='TROCA_VENDEDOR').sum():>5}  (cliente realmente passa de uma pessoa pra outra)

Os {(m['status']=='TROCA_VENDEDOR').sum()} clientes em TROCA_VENDEDOR sao os mais importantes
de revisar — sao casos em que o cliente passa de um vendedor para outro
totalmente diferente. Filtrar status='TROCA_VENDEDOR' no CSV.
"""
print(readme_extra)
