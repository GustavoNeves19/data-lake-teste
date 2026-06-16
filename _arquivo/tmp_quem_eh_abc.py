"""Valida quem é Vendedor A/B/C da planilha HOSPITALAR — via cruzamento com CRM owner."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

pd.set_option('display.width', 220)
pd.set_option('display.max_colwidth', 70)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

# 1) Carrega CRM bridge + owner em pandas
print('Carregando bridge + CRM owners...')
crm = c.query("""
SELECT
  UPPER(TRIM(b.partner_name)) AS nome_norm,
  b.partner_code,
  u.name AS vend_crm
FROM `sapient-metrics-492914-m7.silver_comercial.param_com_entity_bridge` b
LEFT JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_organization` o ON o.org_id = b.org_id
LEFT JOIN `sapient-metrics-492914-m7.crm_raw.dim_crm_user` u ON u.user_id = o.owner_id
WHERE b.is_active = TRUE AND b.partner_name IS NOT NULL
""").to_dataframe()
print(f'  {len(crm)} mapeamentos partner↔owner carregados')

# 2) Para cada aba A/B/C, ler clientes e cruzar
path = r'C:\Users\gusta\Downloads\RFV Hospitalar 01-04-2025 até 30-04-2026 (1).xlsx'
abas = {'A': 'Sem fórmula Vendedor A', 'B': 'Sem fórmula Vendedor B', 'C': 'Sem fórmula Vendedor C'}

print('\n' + '=' * 100)
print('QUEM É VENDEDOR A, B, C DA PLANILHA HOSPITALAR (segundo o CRM owner)?')
print('=' * 100)

for cod, sheet in abas.items():
    df = pd.read_excel(path, sheet_name=sheet)
    col = df.columns[0]
    clientes_plan = df[col].dropna().astype(str).str.upper().str.strip().unique()
    clientes_df = pd.DataFrame({'nome_norm': clientes_plan})

    merged = clientes_df.merge(crm, on='nome_norm', how='left')
    dist = merged.groupby('vend_crm', dropna=False).size().reset_index(name='clientes').sort_values('clientes', ascending=False)

    print(f'\n--- Vendedor {cod} (planilha) — {len(clientes_plan)} clientes ---')
    print(dist.to_string(index=False))

    dist_known = dist[dist['vend_crm'].notna()].copy()
    if not dist_known.empty:
        dominante = dist_known.iloc[0]
        pct = dominante['clientes'] / len(clientes_plan) * 100
        print(f'\n  ==> DOMINANTE no CRM: "{dominante["vend_crm"]}" ({dominante["clientes"]}/{len(clientes_plan)} = {pct:.1f}%)')
        print(f'      Mapeamento atual do populate_carteira.py: Vendedor {cod} = {"Guilherme" if cod=="A" else ("Kaua" if cod=="B" else "Richard")}')
