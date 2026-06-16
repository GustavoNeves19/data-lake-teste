"""
Análise Exploratória — Umbler Talk (Bronze)
Lê de umbler_raw no BigQuery e imprime insights principais.
"""
from __future__ import annotations

import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google.cloud import bigquery
from google.oauth2 import service_account

# ── Config ────────────────────────────────────────────────────────────────────

PROJECT    = "sapient-metrics-492914-m7"
DATASET    = "umbler_raw"
CREDS_PATH = r"C:\teste\sapient-metrics.json"

CHANNEL_MAP = {
    "aOe5ExEkeQjqJZZq": "Comercial (Broker)",
    "absDYbtO-13jxppl": "Comercial (API ✅)",
    "aO_y1RR8eR9Y_p3X": "SAC (Broker)",
    "abvbC3AlHqlU1EVJ": "SAC - Nevoni (API ✅)",
    "aPEHVhR8eR9YRfnx": "Farmácias (Broker)",
    "abvbdQ1XUzAA-ajB": "Farmácias (API - inativo)",
    "ad0UBzg21C6QgYpq": "Farmácias (API - aguardando)",
    "acqGB_4hy6-aB1ZH": "VanguardIA Teste",
}

# Campos reais do payload (aninhados)
# channel  → $.channel.id  / $.channel.channelType / $.channel.name
# sector   → $.sector.id   / $.sector.name
# open     → $.open         (true = aberto, false = encerrado)
# waiting  → $.waiting      (true = aguardando resposta do atendente)
# totalUnread → $.totalUnread

creds  = service_account.Credentials.from_service_account_file(CREDS_PATH)
client = bigquery.Client(project=PROJECT, credentials=creds)


def query(sql: str):
    return list(client.query(sql).result())


def sep(title=""):
    width = 62
    if title:
        pad = max((width - len(title) - 2) // 2, 1)
        print(f"\n{'─' * pad} {title} {'─' * pad}")
    else:
        print("─" * width)


bar_max = 35

# ══════════════════════════════════════════════════════════════════════════════
# 1. CANAIS
# ══════════════════════════════════════════════════════════════════════════════

sep("CANAIS")

channels_rows = query(f"""
SELECT
    JSON_VALUE(payload_json, '$.id')            AS id,
    JSON_VALUE(payload_json, '$.name')          AS name,
    JSON_VALUE(payload_json, '$.channelType')   AS channel_type,
    JSON_VALUE(payload_json, '$.state')         AS state,
    JSON_VALUE(payload_json, '$.phoneNumber')   AS phone
FROM `{PROJECT}.{DATASET}.channels`
ORDER BY name
""")

print(f"\nTotal de canais: {len(channels_rows)}\n")
print(f"  {'Nome':<32} {'Tipo':<22} {'Estado':<18} {'Telefone'}")
print(f"  {'─'*32} {'─'*22} {'─'*18} {'─'*15}")
for r in channels_rows:
    print(f"  {(r.name or ''):<32} {(r.channel_type or ''):<22} {(r.state or ''):<18} {r.phone or ''}")


# ══════════════════════════════════════════════════════════════════════════════
# 2. SETORES
# ══════════════════════════════════════════════════════════════════════════════

sep("SETORES")

sectors_rows = query(f"""
SELECT
    JSON_VALUE(payload_json, '$.id')   AS id,
    JSON_VALUE(payload_json, '$.name') AS name
FROM `{PROJECT}.{DATASET}.sectors`
ORDER BY name
""")
sector_name_map = {r.id: r.name for r in sectors_rows}

print(f"\nTotal de setores: {len(sectors_rows)}")
for r in sectors_rows:
    print(f"  • {r.name}")


# ══════════════════════════════════════════════════════════════════════════════
# 3. TAGS
# ══════════════════════════════════════════════════════════════════════════════

sep("TAGS")

tags_rows = query(f"""
SELECT
    JSON_VALUE(payload_json, '$.name')  AS name,
    JSON_VALUE(payload_json, '$.color') AS color
FROM `{PROJECT}.{DATASET}.tags`
ORDER BY name
""")
print(f"\nTotal de tags: {len(tags_rows)}")
for r in tags_rows:
    print(f"  • {r.name}  ({r.color or 'sem cor'})")


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONTATOS
# ══════════════════════════════════════════════════════════════════════════════

sep("CONTATOS")

contacts_total = query(f"""
SELECT COUNT(*) AS total FROM `{PROJECT}.{DATASET}.contacts`
""")[0].total

contacts_named = query(f"""
SELECT
    COUNTIF(TRIM(COALESCE(JSON_VALUE(payload_json, '$.name'), '')) != '') AS com_nome,
    COUNTIF(TRIM(COALESCE(JSON_VALUE(payload_json, '$.name'), '')) =  '') AS sem_nome
FROM `{PROJECT}.{DATASET}.contacts`
""")[0]

contacts_activity = query(f"""
SELECT
    COUNTIF(TIMESTAMP(JSON_VALUE(payload_json, '$.lastActiveUTC'))
            >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30  DAY)) AS ativos_30d,
    COUNTIF(TIMESTAMP(JSON_VALUE(payload_json, '$.lastActiveUTC'))
            >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90  DAY)) AS ativos_90d,
    COUNTIF(TIMESTAMP(JSON_VALUE(payload_json, '$.lastActiveUTC'))
            >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)) AS ativos_180d
FROM `{PROJECT}.{DATASET}.contacts`
WHERE JSON_VALUE(payload_json, '$.lastActiveUTC') IS NOT NULL
""")[0]

print(f"\nTotal de contatos  : {contacts_total:,}")
print(f"Com nome cadastrado: {contacts_named.com_nome:,}  ({contacts_named.com_nome/contacts_total*100:.1f}%)")
print(f"Sem nome           : {contacts_named.sem_nome:,}  ({contacts_named.sem_nome/contacts_total*100:.1f}%)")
print(f"\nAtividade (dias corridos a partir de hoje):")
print(f"  Últimos 30 dias : {contacts_activity.ativos_30d:,}")
print(f"  Últimos 90 dias : {contacts_activity.ativos_90d:,}")
print(f"  Últimos 180 dias: {contacts_activity.ativos_180d:,}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. CHATS — visão geral
# ══════════════════════════════════════════════════════════════════════════════

sep("CHATS — VISÃO GERAL")

# campos reais: open=true/false, waiting=true/false, totalUnread, closedAtUTC
chats_summary = query(f"""
SELECT
    COUNT(*)                                                                       AS total,
    MIN(TIMESTAMP(JSON_VALUE(payload_json, '$.createdAtUTC')))                     AS mais_antigo,
    MAX(TIMESTAMP(JSON_VALUE(payload_json, '$.eventAtUTC')))                       AS mais_recente,
    COUNTIF(JSON_VALUE(payload_json, '$.open') = 'true')                           AS abertos,
    COUNTIF(JSON_VALUE(payload_json, '$.open') = 'false'
            OR JSON_VALUE(payload_json, '$.closedAtUTC') IS NOT NULL)              AS encerrados,
    COUNTIF(JSON_VALUE(payload_json, '$.waiting') = 'true')                        AS aguardando_atendimento,
    COUNTIF(SAFE_CAST(JSON_VALUE(payload_json, '$.totalUnread') AS INT64) > 0)     AS com_nao_lidas,
    SUM(SAFE_CAST(JSON_VALUE(payload_json, '$.totalUnread') AS INT64))             AS total_nao_lidas
FROM `{PROJECT}.{DATASET}.chats`
""")[0]

print(f"\nTotal de conversas         : {chats_summary.total:,}")
print(f"Conversa mais antiga       : {str(chats_summary.mais_antigo)[:10]}")
print(f"Última atividade           : {str(chats_summary.mais_recente)[:10]}")
print(f"Em aberto (open=true)      : {chats_summary.abertos:,}  ({chats_summary.abertos/chats_summary.total*100:.1f}%)")
print(f"Encerrados                 : {chats_summary.encerrados:,}  ({chats_summary.encerrados/chats_summary.total*100:.1f}%)")
print(f"Aguardando atendimento     : {chats_summary.aguardando_atendimento:,}  ({chats_summary.aguardando_atendimento/chats_summary.total*100:.1f}%)")
print(f"Com mensagens não lidas    : {chats_summary.com_nao_lidas:,}")
print(f"Total msgs não lidas       : {chats_summary.total_nao_lidas:,}")


# ══════════════════════════════════════════════════════════════════════════════
# 6. CHATS — por canal (campo aninhado: $.channel.id / $.channel.channelType)
# ══════════════════════════════════════════════════════════════════════════════

sep("CHATS POR CANAL")

chats_by_channel = query(f"""
SELECT
    JSON_VALUE(payload_json, '$.channel.id')          AS channel_id,
    JSON_VALUE(payload_json, '$.channel.name')        AS channel_name,
    JSON_VALUE(payload_json, '$.channel.channelType') AS channel_type,
    COUNT(*)                                           AS total,
    COUNTIF(JSON_VALUE(payload_json, '$.waiting') = 'true')                       AS aguardando,
    SUM(SAFE_CAST(JSON_VALUE(payload_json, '$.totalUnread') AS INT64))             AS total_nao_lidas
FROM `{PROJECT}.{DATASET}.chats`
GROUP BY 1, 2, 3
ORDER BY 4 DESC
""")

print(f"\n  {'Canal':<28} {'Tipo':<16} {'Total':>7}  {'Aguard.':>8}  {'Não lidas':>10}")
print(f"  {'─'*28} {'─'*16} {'─'*7}  {'─'*8}  {'─'*10}")
for r in chats_by_channel:
    label = r.channel_name or CHANNEL_MAP.get(r.channel_id, r.channel_id or "?")
    ctype = r.channel_type or ""
    print(f"  {label:<28} {ctype:<16} {r.total:>7,}  {r.aguardando:>8,}  {(r.total_nao_lidas or 0):>10,}")


# ══════════════════════════════════════════════════════════════════════════════
# 7. CHATS — por setor (campo aninhado: $.sector.name)
# ══════════════════════════════════════════════════════════════════════════════

sep("CHATS POR SETOR")

chats_by_sector = query(f"""
SELECT
    COALESCE(JSON_VALUE(payload_json, '$.sector.name'), 'sem setor') AS sector_name,
    COUNT(*)                                                           AS total,
    COUNTIF(JSON_VALUE(payload_json, '$.waiting') = 'true')           AS aguardando,
    SUM(SAFE_CAST(JSON_VALUE(payload_json, '$.totalUnread') AS INT64)) AS total_nao_lidas
FROM `{PROJECT}.{DATASET}.chats`
GROUP BY 1
ORDER BY 2 DESC
""")

print(f"\n  {'Setor':<22} {'Total':>7}  {'Aguard.':>8}  {'Não lidas':>10}")
print(f"  {'─'*22} {'─'*7}  {'─'*8}  {'─'*10}")
for r in chats_by_sector:
    print(f"  {r.sector_name:<22} {r.total:>7,}  {r.aguardando:>8,}  {(r.total_nao_lidas or 0):>10,}")


# ══════════════════════════════════════════════════════════════════════════════
# 8. CHATS — por mês (volume criado)
# ══════════════════════════════════════════════════════════════════════════════

sep("CHATS POR MÊS (volume criado)")

chats_by_month = query(f"""
SELECT
    FORMAT_TIMESTAMP('%Y-%m', TIMESTAMP(JSON_VALUE(payload_json, '$.createdAtUTC'))) AS mes,
    COUNT(*) AS total,
    COUNTIF(JSON_VALUE(payload_json, '$.waiting') = 'true') AS aguardando
FROM `{PROJECT}.{DATASET}.chats`
WHERE JSON_VALUE(payload_json, '$.createdAtUTC') IS NOT NULL
GROUP BY 1
ORDER BY 1
""")

print()
max_val = max(r.total for r in chats_by_month) if chats_by_month else 1
for r in chats_by_month:
    bar = "█" * int(r.total / max_val * bar_max)
    print(f"  {r.mes}  {bar:<35}  {r.total:>5,}  ({r.aguardando} aguardando)")


# ══════════════════════════════════════════════════════════════════════════════
# 9. CHATS — por dia da semana
# ══════════════════════════════════════════════════════════════════════════════

sep("VOLUME POR DIA DA SEMANA")

chats_by_dow = query(f"""
SELECT
    FORMAT_TIMESTAMP('%u', TIMESTAMP(JSON_VALUE(payload_json, '$.createdAtUTC'))) AS dow_num,
    FORMAT_TIMESTAMP('%A', TIMESTAMP(JSON_VALUE(payload_json, '$.createdAtUTC'))) AS dow_name,
    COUNT(*) AS total
FROM `{PROJECT}.{DATASET}.chats`
WHERE JSON_VALUE(payload_json, '$.createdAtUTC') IS NOT NULL
GROUP BY 1, 2
ORDER BY 1
""")

DOW_PT = {
    "Monday":"Segunda","Tuesday":"Terça","Wednesday":"Quarta",
    "Thursday":"Quinta","Friday":"Sexta","Saturday":"Sábado","Sunday":"Domingo"
}

print()
max_val = max(r.total for r in chats_by_dow) if chats_by_dow else 1
for r in chats_by_dow:
    nome = DOW_PT.get(r.dow_name, r.dow_name)
    bar  = "█" * int(r.total / max_val * bar_max)
    print(f"  {nome:<10}  {bar:<35}  {r.total:>5,}")


# ══════════════════════════════════════════════════════════════════════════════
# 10. TEMPO MÉDIO DE ESPERA (waitingSinceUTC → eventAtUTC como proxy)
# ══════════════════════════════════════════════════════════════════════════════

sep("CONVERSAS AGUARDANDO — TEMPO EM FILA")

waiting_time = query(f"""
SELECT
    JSON_VALUE(payload_json, '$.channel.name')    AS canal,
    JSON_VALUE(payload_json, '$.sector.name')     AS setor,
    COUNT(*)                                       AS qtd_aguardando,
    ROUND(AVG(
        TIMESTAMP_DIFF(
            CURRENT_TIMESTAMP(),
            TIMESTAMP(JSON_VALUE(payload_json, '$.waitingSinceUTC')),
            MINUTE
        )
    ) / 60.0, 1)                                  AS media_horas_espera,
    MAX(
        TIMESTAMP_DIFF(
            CURRENT_TIMESTAMP(),
            TIMESTAMP(JSON_VALUE(payload_json, '$.waitingSinceUTC')),
            HOUR
        )
    )                                              AS max_horas_espera
FROM `{PROJECT}.{DATASET}.chats`
WHERE JSON_VALUE(payload_json, '$.waiting') = 'true'
  AND JSON_VALUE(payload_json, '$.waitingSinceUTC') IS NOT NULL
GROUP BY 1, 2
ORDER BY 4 DESC
""")

if waiting_time:
    print(f"\n  {'Canal':<28} {'Setor':<15} {'Qtd':>5}  {'Média (h)':>10}  {'Máx (h)':>8}")
    print(f"  {'─'*28} {'─'*15} {'─'*5}  {'─'*10}  {'─'*8}")
    for r in waiting_time:
        print(f"  {(r.canal or '?'):<28} {(r.setor or '?'):<15} {r.qtd_aguardando:>5,}  {(r.media_horas_espera or 0):>10.1f}h  {(r.max_horas_espera or 0):>7}h")
else:
    print("\n  Nenhuma conversa em estado 'waiting' no momento.")


# ══════════════════════════════════════════════════════════════════════════════
# 11. TOP CONTATOS (mais conversas)
# ══════════════════════════════════════════════════════════════════════════════

sep("TOP 10 CONTATOS POR VOLUME DE CONVERSAS")

top_contacts = query(f"""
SELECT
    JSON_VALUE(payload_json, '$.contact.name')        AS nome,
    JSON_VALUE(payload_json, '$.contact.phoneNumber') AS telefone,
    COUNT(*)                                           AS total_chats,
    SUM(SAFE_CAST(JSON_VALUE(payload_json, '$.totalUnread') AS INT64)) AS total_nao_lidas
FROM `{PROJECT}.{DATASET}.chats`
WHERE JSON_VALUE(payload_json, '$.contact.name') IS NOT NULL
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 10
""")

print(f"\n  {'Contato':<30} {'Telefone':<16} {'Chats':>6}  {'Não lidas':>10}")
print(f"  {'─'*30} {'─'*16} {'─'*6}  {'─'*10}")
for r in top_contacts:
    print(f"  {(r.nome or ''):<30} {(r.telefone or ''):<16} {r.total_chats:>6,}  {(r.total_nao_lidas or 0):>10,}")


# ══════════════════════════════════════════════════════════════════════════════
# 12. TAGS MAIS USADAS NOS CONTATOS
# ══════════════════════════════════════════════════════════════════════════════

sep("TAGS DOS CONTATOS (via chats)")

tags_in_chats = query(f"""
SELECT
    tag.name AS tag_name,
    COUNT(*) AS qtd_chats
FROM `{PROJECT}.{DATASET}.chats`,
UNNEST(JSON_QUERY_ARRAY(payload_json, '$.contact.tags')) AS tag_json,
UNNEST([STRUCT(JSON_VALUE(tag_json, '$.name') AS name)])  AS tag
WHERE tag.name IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
""")

print()
if tags_in_chats:
    max_val = max(r.qtd_chats for r in tags_in_chats) if tags_in_chats else 1
    for r in tags_in_chats:
        bar = "█" * int(r.qtd_chats / max_val * bar_max)
        print(f"  {r.tag_name:<20}  {bar:<35}  {r.qtd_chats:>5,}")
else:
    print("  Nenhuma tag encontrada nos contatos dos chats.")


# ══════════════════════════════════════════════════════════════════════════════
# FIM
# ══════════════════════════════════════════════════════════════════════════════

sep()
print("\n✅  Análise concluída.\n")
