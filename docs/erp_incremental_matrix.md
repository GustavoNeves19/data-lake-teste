# Matriz de Sincronização Bronze ERP — Estratégia Real

Atualizada em 2026-05-14. Reflete o `sync_mode` configurado em `config/settings.py`.

## Resumo Executivo

| Estratégia | Entidades | Lógica |
|---|---|---|
| `full_snapshot` | 21 | `WRITE_TRUNCATE` a cada execução — espelha o estado atual do ERP |
| `incremental` | 18 | `WRITE_APPEND` com watermark `updated_at_erp` — só carrega registros novos/alterados |

**Tempo estimado por execução diária:**
- Carga histórica inicial (primeira vez): ~3h (full snapshot de tudo com `py -3 main.py`)
- Rotina diária após catch-up: **~15–25 minutos** (`py -3 main.py --incremental`)

---

## Por que estratégias diferentes?

### Full Snapshot — quando usar
Obrigatório quando o ERP **apaga fisicamente registros** ou quando a tabela é pequena o suficiente para recarregar por completo sem custo.

- **PRODUÇÃO:** Ordens de produção são **deletadas do ERP quando finalizadas**. Um `--incremental` não capturaria as exclusões — a bronze ficaria com registros fantasma. Full snapshot espelha o estado atual com zero risco.
- **DIMS:** Tabelas de dimensão são pequenas (<50K linhas) e usam soft-delete no ERP (`YDATEXC`). Um incremental que captura a atualização do soft-delete ainda filtra o registro com `WHERE YDATEXC IS NULL`, deixando o registro "invisível" para o pipeline. Full snapshot é mais seguro e tem custo desprezível.
- **SNAPSHOT_INVENTORY_BALANCE:** Por definição é uma fotografia do saldo atual — sempre full snapshot.

### Incremental — quando usar
Seguro para tabelas de **fatos transacionais** que acumulam registros e nunca deletam fisicamente, onde o custo de recarregar tudo diariamente seria alto.

- Registros financeiros (`fact_payable`, `fact_receivable`, `fact_settled_title`) — títulos são liquidados/cancelados via atualização, não deletados.
- Pedidos (`fact_sales_order`, `fact_purchase_order`, `fact_order_item`) — cancelamentos atualizam o status, não deletam o pedido.
- Movimentações de estoque (`fact_inventory_movement`) — cada movimentação é um registro permanente; quando produção conclui, **registra** novas movimentações (não apaga as anteriores).
- Seriais (`fact_serial_number`, `fact_serial_history`) — as maiores tabelas do ERP (~2M linhas); seguras para incremental.

---

## Tabelas Full Snapshot (21 entidades)

> `sync_mode` não definido ou `"full_snapshot"` → sempre `WRITE_TRUNCATE`

| Domínio | Entidade | Tipo | Motivo |
|---|---|---|---|
| PARTNERS | dim_company | DIM | Pequena, soft-delete |
| PARTNERS | dim_partner | DIM | Pequena, soft-delete |
| PARTNERS | dim_carrier | DIM | Pequena, soft-delete |
| PARTNERS | dim_salesperson | DIM | Pequena, soft-delete |
| PARTNERS | dim_salesperson_group | DIM | Pequena, soft-delete |
| PRODUCTS | dim_family | DIM | Pequena, soft-delete |
| PRODUCTS | dim_group | DIM | Pequena, soft-delete |
| PRODUCTS | dim_item | DIM | Pequena, soft-delete |
| PRODUCTS | dim_material | DIM | Pequena, soft-delete |
| PRODUCTS | dim_tax_classification | DIM | Pequena, soft-delete |
| ORDERS | dim_operation_nature | DIM | Pequena, soft-delete |
| ORDERS | dim_payment_condition | DIM | Pequena, soft-delete |
| INVENTORY | dim_batch | DIM | Pequena, soft-delete |
| INVENTORY | snapshot_inventory_balance | SNAPSHOT | **Por definição** foto do saldo atual |
| PAYMENTS | dim_bank | DIM | Pequena, soft-delete |
| PAYMENTS | dim_department | DIM | Pequena, soft-delete |
| PAYMENTS | dim_financial_item | DIM | Pequena, soft-delete |
| PAYMENTS | dim_surcharge_type | DIM | Pequena, soft-delete |
| PRODUCTION | fact_production_order | FACT | **ERP deleta quando finalizada** |
| PRODUCTION | fact_production_item | FACT | **ERP deleta quando finalizada** |
| PRODUCTION | fact_production_comp_item | FACT | **ERP deleta quando finalizada** |

---

## Tabelas Incrementais (18 entidades)

> `"sync_mode": "incremental"` em `settings.py` → `WRITE_APPEND` com watermark

**Mecanismo:** O pipeline consulta `MAX(updated_at_erp)` no BigQuery, deleta a última janela (`DELETE WHERE updated_at_erp >= max_watermark`) e reapendiciona tudo acima desse ponto. Isso garante que atualizações recentes sobrescrevam versões antigas.

| Domínio | Entidade | Tipo | Coluna Watermark | Linhas (~) | Ganho diário |
|---|---|---|---|---|---|
| PRODUCTS | fact_serial_number | FACT | updated_at_erp | 1.040.000 | Alta |
| PRODUCTS | fact_serial_history | FACT | updated_at_erp | 950.000 | Alta |
| PRODUCTS | bridge_item_bom | BRIDGE | updated_at_erp | ~5.000 | Baixa |
| QUOTES | fact_quote | FACT | updated_at_erp | ~274.000 | Média |
| QUOTES | fact_quote_item | FACT | updated_at_erp | ~274.000 | Média |
| ORDERS | fact_purchase_order | FACT | updated_at_erp | ~200.000 | Média |
| ORDERS | fact_sales_order | FACT | updated_at_erp | ~200.000 | Média |
| ORDERS | fact_order_item | FACT | updated_at_erp | ~200.000 | Média |
| ORDERS | fact_tax_ledger | FACT | updated_at_erp | ~50.000 | Baixa |
| INVENTORY | fact_inventory_movement | FACT | updated_at_erp | 1.100.000 | Alta |
| INVENTORY | bridge_order_batch | BRIDGE | updated_at_erp | ~30.000 | Baixa |
| IMPORTS | fact_import_process | FACT | updated_at_erp | <1.000 | Desprezível |
| IMPORTS | fact_import_order | FACT | updated_at_erp | <1.000 | Desprezível |
| IMPORTS | fact_import_item | FACT | updated_at_erp | <1.000 | Desprezível |
| IMPORTS | fact_import_installment | FACT | updated_at_erp | <1.000 | Desprezível |
| PAYMENTS | fact_payable | FACT | updated_at_erp | ~100.000 | Média |
| PAYMENTS | fact_receivable | FACT | updated_at_erp | ~100.000 | Média |
| PAYMENTS | fact_settled_title | FACT | updated_at_erp | ~150.000 | Média |

---

## Comandos Operacionais

### Carga histórica (primeira vez / catch-up de meses)
```bash
# Carrega TUDO do ERP do zero — leva ~3h
# Necessário quando o BQ está desatualizado por semanas/meses
py -3 main.py
```

### Rotina diária (após primeira carga ou catch-up)
```bash
# Incremental para facts | full snapshot para dims e produção
# Tempo estimado: 15-25 minutos
py -3 main.py --incremental
```

### Carga de um domínio específico (quando necessário)
```bash
py -3 main.py --domain ORDERS
py -3 main.py --domain PAYMENTS
py -3 main.py --domain PRODUCTS
```

### Automação via Windows Task Scheduler
```powershell
# Rodar UMA VEZ como Administrador para registrar a tarefa diária às 06:00
powershell -ExecutionPolicy Bypass -File .\scripts\setup_daily_task.ps1

# Testar execução imediata
Start-ScheduledTask -TaskName "DataLake_ERP_DailySync"

# Ver logs
Get-Content .\logs\erp_sync_*.log -Tail 50
```

---

## Ordem de catch-up recomendada (Mai/2026)

Dados atualizados até 12/05 no SQL Server, BQ está em 08/02.

1. **Rodar `py -3 main.py` uma vez** → carga full snapshot de tudo (espera ~3h)
   - Isso garante que dims, produção e snapshot_inventory_balance estão 100% corretos
   - As facts também serão carregadas completas desta vez
2. **Configurar Task Scheduler** com `setup_daily_task.ps1`
3. **A partir de amanhã**, o Task Scheduler roda `py -3 main.py --incremental` às 06:00 diariamente

---

## Notas de Segurança do Incremental

- **Deleções em facts**: Para `fact_sales_order` e similares, se um pedido for cancelado no ERP (soft-delete via `YDATEXC`), ele ainda aparece no BQ porque foi filtrado da query incremental. A camada Silver deve tratar status de cancelamento, não depender da ausência do registro.
- **Janela de recarga**: O pipeline apaga e reapendiciona a faixa `>= MAX(updated_at_erp)` antes de inserir. Isso cobre registros editados retroativamente no mesmo dia.
- **Produção sempre espelhada**: `fact_production_*` sempre reflete o estado atual do ERP — ordens concluídas somem da bronze assim como somem do ERP.
