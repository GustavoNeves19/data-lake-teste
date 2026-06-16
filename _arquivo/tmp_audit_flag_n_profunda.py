"""Investiga as 297 naturezas YENTSAI=S + YFINNAT=N para separar:
   - Devolução legítima (DEVE excluir)
   - Movimento administrativo (DEVE excluir)
   - Venda mal-classificada (DEVERIA entrar)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
from extract.sqlserver import SQLServerExtractor

pd.set_option('display.width', 240)
pd.set_option('display.max_colwidth', 60)
pd.set_option('display.max_rows', 200)

creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
c = bigquery.Client(credentials=creds, project='sapient-metrics-492914-m7')

ex = SQLServerExtractor()
ex.connect()

# 1) Pega naturezas S+N com info adicional
df = pd.read_sql("""
SELECT
  YCODNAT,
  YNOMNAT,
  YFINNAT,
  YDEVNAT,         -- flag de devolução
  YESTNAT,         -- flag de movimentação estoque
  YTIPMOV,         -- tipo movimento
  YIMPNAT          -- imprime nota?
FROM [NATUREZAS DE OPERAÇÕES]
WHERE YENTSAI = 'S' AND YFINNAT = 'N' AND YDATEXC IS NULL
ORDER BY YCODNAT
""", ex._conn)

# 2) Pega valor real movimentado em 12 meses
codes = ','.join(f"'{c}'" for c in df['YCODNAT'])
df_val = c.query(f"""
SELECT
  nature_code AS YCODNAT,
  COUNT(*) AS pedidos,
  COUNT(DISTINCT partner_code) AS clientes,
  ROUND(SUM(total_amount), 0) AS valor_12m
FROM `sapient-metrics-492914-m7.dm_orders.fact_sales_order`
WHERE nature_code IN ({codes})
  AND order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
GROUP BY 1
""").to_dataframe()
df_val['YCODNAT'] = df_val['YCODNAT'].astype(str).str.strip()
df['YCODNAT'] = df['YCODNAT'].astype(str).str.strip()
m = df.merge(df_val, on='YCODNAT', how='left').fillna({'pedidos': 0, 'clientes': 0, 'valor_12m': 0})

# 3) Classifica cada natureza
def categorizar(r):
    nome = str(r['YNOMNAT']).upper()
    if r['YDEVNAT'] == 'S':
        return 'A_DEVOLUCAO'
    if any(w in nome for w in ['SAIDA RH','SAIDA INFORMATICA','SAIDA ADMINIS','SAIDA COMERCIAL',
                                'SAIDA RECEPCAO','SAIDA CONTABIL','SAIDA CONTAS','SAIDA EXPEDICAO',
                                'SAIDA FATURAMENTO','SAIDA TELEVENDAS','SAIDA ALMOXARIFADO',
                                'SAIDA INALADOR','SAIDA CONSERVACAO','SAIDA QUALIDADE',
                                'SAIDA ASSISTENCIA','SAIDA REPRESENTANTES','SAIDA SAC','SAIDA COMPRAS',
                                'SAIDA CONVENCIONAL','SAIDA GERAL']):
        return 'B_SAIDA_ADMIN'
    if any(w in nome for w in ['REMESSA', 'BONIFICACAO', 'DEMONSTRACAO', 'COMODATO',
                                'CONSIGNACAO', 'INDUSTRIALIZACAO', 'RETORNO',
                                'TRANSFERENCIA', 'BRINDE', 'AMOSTRA']):
        return 'C_REMESSA_BONIF'
    if 'INATIVO' in nome:
        return 'D_INATIVA'
    if any(w in nome for w in ['VENDA', 'REVENDA', 'NOTA FISCAL', 'NF']):
        return 'E_PARECE_VENDA'
    return 'F_OUTROS'

m['categoria'] = m.apply(categorizar, axis=1)

print('=' * 100)
print('CATEGORIZACAO das 297 naturezas SAIDA + flag=N (filtradas hoje)')
print('=' * 100)
print(m.groupby('categoria').agg(
    qtd=('YCODNAT','count'),
    valor_12m=('valor_12m','sum'),
).sort_values('valor_12m', ascending=False).to_string())

# 4) CATEGORIA E (parece venda) — atenção dobrada!
print('\n' + '=' * 100)
print('⚠ CATEGORIA E — "PARECE VENDA" mas está filtrada como N (top 30 por valor)')
print('=' * 100)
e = m[m['categoria'] == 'E_PARECE_VENDA'].sort_values('valor_12m', ascending=False)
print(e[['YCODNAT','YNOMNAT','YDEVNAT','YESTNAT','pedidos','valor_12m']].head(30).to_string(index=False))
print(f'\nTOTAL categoria E (suspeitas): R$ {e["valor_12m"].sum():,.0f}')

# 5) CATEGORIA F (outros não classificados) — investigar tambem
print('\n' + '=' * 100)
print('CATEGORIA F — "OUTROS" (top 20)')
print('=' * 100)
f = m[m['categoria'] == 'F_OUTROS'].sort_values('valor_12m', ascending=False)
print(f[['YCODNAT','YNOMNAT','YDEVNAT','YESTNAT','pedidos','valor_12m']].head(20).to_string(index=False))
print(f'\nTOTAL categoria F: R$ {f["valor_12m"].sum():,.0f}')

# 6) Resumo: quanto perdemos legitimamente vs erro de classificação
print('\n' + '=' * 100)
print('RESUMO METODOLOGICO')
print('=' * 100)
total = m['valor_12m'].sum()
adm   = m[m['categoria']=='B_SAIDA_ADMIN']['valor_12m'].sum()
dev   = m[m['categoria']=='A_DEVOLUCAO']['valor_12m'].sum()
rem   = m[m['categoria']=='C_REMESSA_BONIF']['valor_12m'].sum()
inat  = m[m['categoria']=='D_INATIVA']['valor_12m'].sum()
venda = m[m['categoria']=='E_PARECE_VENDA']['valor_12m'].sum()
outr  = m[m['categoria']=='F_OUTROS']['valor_12m'].sum()
print(f'  Total filtrado (12m):                       R$ {total:>13,.0f}')
print(f'  Devolucao (CORRETO excluir):                R$ {dev:>13,.0f}')
print(f'  Saida administrativa (CORRETO excluir):     R$ {adm:>13,.0f}')
print(f'  Remessa/Bonificacao (CORRETO excluir):      R$ {rem:>13,.0f}')
print(f'  Inativas (CORRETO excluir):                 R$ {inat:>13,.0f}')
print(f'  ⚠ Parece VENDA (ATENCAO ALVES):            R$ {venda:>13,.0f}')
print(f'  Outros (REVISAR):                           R$ {outr:>13,.0f}')

# Salva CSV pra revisar com Alves
out = r'C:\Users\gusta\Downloads\auditoria_naturezas_flag_n.csv'
m_out = m[['YCODNAT','YNOMNAT','YDEVNAT','YESTNAT','pedidos','clientes','valor_12m','categoria']].copy()
m_out = m_out.sort_values(['categoria','valor_12m'], ascending=[True, False])
m_out.to_csv(out, index=False, encoding='utf-8-sig')
print(f'\nCSV salvo: {out}')
