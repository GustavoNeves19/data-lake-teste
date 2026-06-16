"""Gera .streamlit/secrets.toml a partir do JSON do service account."""
import json, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

JSON_PATH = r'C:\teste\sapient-metrics.json'
OUT_PATH = '.streamlit/secrets.toml'

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    sa = json.load(f)

lines = [
    '# Gerado automaticamente — cole TUDO abaixo em "Secrets" do Streamlit Cloud',
    '',
    '[gcp_service_account]',
]

for k in [
    'type', 'project_id', 'private_key_id', 'client_email', 'client_id',
    'auth_uri', 'token_uri', 'auth_provider_x509_cert_url',
    'client_x509_cert_url', 'universe_domain',
]:
    v = sa.get(k)
    if v:
        # Em TOML, strings simples só precisam escapar " e \\
        v_esc = str(v).replace('\\', '\\\\').replace('"', '\\"')
        lines.append(f'{k} = "{v_esc}"')

# private_key é multiline — triple-quoted preserva \n da JSON
pk = sa['private_key']
lines.append(f'private_key = """{pk}"""')

# Comentarios para OpenAI
lines.append('')
lines.append('# OpenAI (Oráculo) — opcional. Se vazio, cada user cola sua chave na sidebar.')
lines.append('# OPENAI_API_KEY = "sk-..."')
lines.append('# OPENAI_MODEL   = "gpt-4o-mini"')

os.makedirs('.streamlit', exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print(f'OK gravado em: {os.path.abspath(OUT_PATH)}')
print(f'Tamanho:       {os.path.getsize(OUT_PATH):,} bytes')
print(f'project_id:    {sa["project_id"]}')
print(f'client_email:  {sa["client_email"]}')
