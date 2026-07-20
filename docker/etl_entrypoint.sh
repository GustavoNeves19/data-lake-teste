#!/bin/sh
# Entrypoint do pipeline ETL no EasyPanel — container SEMPRE de pé, agendador próprio.
# TRÊS cadências (horários em UTC, HH:MM; BRT = UTC menos 3):
#   - COMPLETA (tudo, ~2h): 1x de madrugada. Pros outros setores e pra deixar série/
#     estoque/financeiro frescos.
#   - SINCRONIZAÇÃO ERP (rápida: ERP-comercial PARTNERS/ORDERS/QUOTES + CRM + silver/gold,
#     ~25min): nos horários em que o Fred sobe o ERP (06/09/12/15/17 BRT), mais o delay de
#     ~15min pra carga dele terminar → a gente dispara :20. Aqui o CRM sobe JUNTO com o ERP.
#   - CRM (só Pipedrive bronze, ~5min): de hora em hora, nas horas comerciais que NÃO são de
#     sincronização com o ERP. A Gestão à Vista lê crm_raw direto, então o funil/atividades
#     ficam frescos de hora em hora sem recomputar silver/gold/RFV à toa.
# O agendador é um loop em shell (o cron do Debian não engatilhou em runtime, ver git 18/06);
# loga "próximo: <modo> em ..." todo ciclo, então dá pra ver no log do EasyPanel que está vivo.
# Horários aceitam HH:MM e saem prontos no fuso certo; ajuste pelo Environment se precisar.
set -eu

# ── segredos vindos do ambiente do EasyPanel → arquivos ───────────────────────
if [ -n "${INGESTION_DOTENV:-}" ];    then printf '%s' "$INGESTION_DOTENV"    > /app/.env;         fi
if [ -n "${BQ_CREDENTIALS_JSON:-}" ]; then printf '%s' "$BQ_CREDENTIALS_JSON" > /app/bq_sa.json;   fi
if [ -n "${GMAIL_SA_JSON:-}" ];       then printf '%s' "$GMAIL_SA_JSON"       > /app/gmail_sa.json; fi

# Horários em UTC (HH:MM), separados por espaço. Defaults já no fuso certo (BRT = UTC-3):
#   FULL  06:00 UTC = 03:00 BRT (1x de madrugada).
#   FAST  = sync com o ERP. Fred sobe 06/09/12/15/17 BRT; +15min de carga dele → :20.
#          BRT 06:20/09:20/12:20/15:20/17:20 = UTC 09:20 12:20 15:20 18:20 20:20.
#   CRM   = Pipedrive de hora em hora nas horas comerciais que NÃO têm sync de ERP.
#          BRT 07/08/10/11/13/14/16/18 :20 = UTC 10:20 11:20 13:20 14:20 16:20 17:20 19:20 21:20.
TIMES_FULL="${CRON_TIMES_FULL:-06:00}"
TIMES_FAST="${CRON_TIMES_FAST:-09:20 12:20 15:20 18:20 20:20}"
TIMES_CRM="${CRON_TIMES_CRM:-10:20 11:20 13:20 14:20 16:20 17:20 19:20 21:20}"

CRED="GOOGLE_APPLICATION_CREDENTIALS=/app/bq_sa.json GMAIL_SERVICE_ACCOUNT_FILE=/app/gmail_sa.json"
RUN_FULL="cd /app && ${CRED} python scripts/pipeline_diario.py --execute --include-erp"
RUN_FAST="cd /app && ${CRED} python scripts/pipeline_diario.py --execute --include-erp --fast"
RUN_CRM="cd /app && ${CRED} python scripts/pipeline_diario.py --execute --crm-only"

run_mode() {  # $1 = full | fast | crm
  modo="$1"
  case "$modo" in
    full) cmd="$RUN_FULL" ;;
    fast) cmd="$RUN_FAST" ;;
    *)    cmd="$RUN_CRM"  ;;
  esac
  echo "[scheduler] === disparando ${modo} em $(date -u '+%Y-%m-%d %H:%M:%S') UTC ==="
  if sh -c "$cmd"; then
    echo "[scheduler] ${modo} OK em $(date -u '+%H:%M:%S') UTC"
  else
    echo "[scheduler] ${modo} retornou erro (rc=$?) — segue agendado, próximo ciclo refaz"
  fi
}

# epoch do próximo "HH:MM" (hoje; se já passou, amanhã). Usa $now (definido no laço).
next_epoch() {  # $1 = HH:MM
  t=$(date -u -d "$(date -u +%Y-%m-%d) ${1}:00" +%s)
  [ "$t" -le "$now" ] && t=$((t + 86400))
  echo "$t"
}

# ── execução inicial no deploy: refresh de CRM (rápido, valida que o container subiu) ──
if [ "${RUN_ON_START:-1}" = "1" ]; then
  echo "[entrypoint] execução inicial (RUN_ON_START=1): refresh de CRM..."
  run_mode crm
fi

echo "[scheduler] full=${TIMES_FULL} | fast/ERP=${TIMES_FAST} | crm=${TIMES_CRM} (UTC; BRT=UTC-3). Container de pé."
while :; do
  now=$(date -u +%s)
  next=""; next_mode=""
  for hm in $TIMES_FULL; do t=$(next_epoch "$hm"); if [ -z "$next" ] || [ "$t" -lt "$next" ]; then next=$t; next_mode="full"; fi; done
  for hm in $TIMES_FAST; do t=$(next_epoch "$hm"); if [ -z "$next" ] || [ "$t" -lt "$next" ]; then next=$t; next_mode="fast"; fi; done
  for hm in $TIMES_CRM;  do t=$(next_epoch "$hm"); if [ -z "$next" ] || [ "$t" -lt "$next" ]; then next=$t; next_mode="crm";  fi; done
  sleep_s=$((next - now))
  echo "[scheduler] próximo: ${next_mode} em $(date -u -d "@$next" '+%Y-%m-%d %H:%M') UTC (em ${sleep_s}s)"
  sleep "$sleep_s"
  run_mode "$next_mode"
done
