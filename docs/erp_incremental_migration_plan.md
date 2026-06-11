# Plano Tecnico - Bronze ERP 100% Incremental

## Objetivo

Migrar a bronze SQL do ERP para operacao diaria automatizada com watermark de origem, eliminando o modelo hibrido em que parte das tabelas ainda caia em full refresh.

## Estrategia Tecnica

1. Expor um watermark confiavel em cada entidade SQL do ERP.
2. Priorizar `updated_at_erp` como coluna incremental padrao.
3. Preservar `created_at_erp` nas entidades em que esse campo ja existia, para auditoria.
4. Rodar o pipeline em modo:
   - ler `MAX(watermark)` no BigQuery;
   - extrair do SQL apenas `watermark >= max_bq`;
   - apagar no BigQuery a faixa final reprocessada;
   - recarregar somente esse recorte;
   - continuar as surrogate keys sem colisao.

## Migracao Aplicada

### 1. Pipeline

- `orchestration/pipeline.py`
  - prioridade incremental alterada para usar `updated_at_erp` antes de `created_at_erp`;
  - modo incremental mantido para a bronze inteira via `py -3 main.py --incremental`.

- `extract/sqlserver.py`
  - query incremental encapsulada por entidade com filtro em watermark.

- `load/bigquery.py`
  - leitura de `MAX(coluna)` no BigQuery;
  - `DELETE` da faixa incremental antes do append;
  - suporte a SK sequencial sem colisao em append incremental.

- `transform/transformations.py`
  - surrogate key com offset para append incremental.

### 2. Entidades SQL Migradas

- Dimensoes e cadastros:
  - empresas, parceiros, transportadoras, grupos de atendentes, atendentes
  - familias, grupos, classificacoes fiscais, itens, materiais
  - bancos, setores, itens financeiros, naturezas de operacao, condicoes de pagamento

- Fatos e bridges:
  - pedidos de compra e venda
  - itens de pedido
  - livros fiscais
  - ordens de producao e seus itens
  - movimentacao de estoque
  - saldo de estoque
  - lotes e vinculos de lote
  - historico e cadastro de seriais
  - orcamentos e itens de orcamento
  - processos de importacao, pedidos, itens e parcelas
  - contas a pagar, receber e titulos liquidados
  - surcharge codes derivados

### 3. Configuracao

- `config/settings.py`
  - schemas atualizados para expor `updated_at_erp` nas 39 entidades SQL do ERP;
  - `dim_tax_classification` reabilitada no pipeline.

### 4. Documentacao

- `docs/erp_incremental_matrix.md`
  - estado atual gerado a partir da configuracao real do pipeline;
  - resultado atual: 39 de 39 entidades SQL do ERP em `incremental_real`.

## Comando de Producao

```bash
py -3 main.py --incremental
```

Esse comando agora representa a bronze inteira do ERP em modo incremental diario.

## Validacoes Executadas

- compilacao Python dos arquivos alterados;
- `--help` da CLI;
- validacao SQL das queries alteradas no SQL Server, incluindo checagem da coluna `updated_at_erp`.

## Riscos Residuais

- o watermark depende do comportamento correto de `YDATINC` / `YDATALT` na origem;
- se alguma tabela do ERP deixar de atualizar `YDATALT` em manutencoes futuras, o incremental pode perder mudancas retroativas;
- algumas entidades ainda possuem colunas de schema historicas nao mapeadas pela query, o que nao bloqueia o incremental, mas vale revisar numa etapa de saneamento estrutural.

## Proximo Passo Recomendado

Agendar `py -3 main.py --incremental` em cron ou Task Scheduler e monitorar por alguns dias:

- tempo total de execucao;
- volume incremental por entidade;
- eventuais lacunas de watermark;
- custo de BigQuery e estabilidade do delete + append da faixa final.
