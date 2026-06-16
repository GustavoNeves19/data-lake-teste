"""
Analisa os padrões de '?' restantes em dim_partner
para identificar os nomes próprios mais frequentes a corrigir.
"""
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from google.cloud import bigquery
from google.oauth2 import service_account
from collections import Counter

PROJ = "sapient-metrics-492914-m7"
creds = service_account.Credentials.from_service_account_file(
    r'C:\teste\sapient-metrics.json',
    scopes=['https://www.googleapis.com/auth/cloud-platform'])
client = bigquery.Client(credentials=creds, project=PROJ)

df = client.query(f"""
    SELECT partner_name FROM `{PROJ}.dm_partners.dim_partner`
    WHERE partner_name LIKE '%?%'
    ORDER BY partner_name
""").to_dataframe()

print(f"Total nomes corrompidos em dim_partner: {len(df)}\n")

# Extrai tokens com '?'
tokens_with_q = Counter()
start_patterns = Counter()  # padrões que COMEÇAM com ?

for name in df['partner_name']:
    words = name.split()
    for w in words:
        if '?' in w:
            tokens_with_q[w] += 1
    if name.startswith('?'):
        # Pega o primeiro "token" de nome
        start_patterns[words[0]] += 1

print("=== Top 50 tokens com '?' (mais frequentes) ===")
for tok, cnt in tokens_with_q.most_common(50):
    print(f"  {cnt:4d}x  '{tok}'")

print()
print("=== Tokens que COMEÇAM com '?' (mais frequentes) ===")
for tok, cnt in start_patterns.most_common(30):
    print(f"  {cnt:4d}x  '{tok}'")

print()
print("=== Padrão geral: posição do '?' no nome ===")
pos_first = Counter()
pos_last = Counter()
for name in df['partner_name']:
    for i, c in enumerate(name):
        if c == '?':
            pos_first['inicio' if i == 0 else ('fim' if i == len(name)-1 else 'meio')] += 1

for p, cnt in pos_first.most_common():
    print(f"  {p}: {cnt}")

print()
print("=== Amostra completa (primeiros 60 nomes) ===")
for name in sorted(df['partner_name'])[:60]:
    print(f"  {name}")
