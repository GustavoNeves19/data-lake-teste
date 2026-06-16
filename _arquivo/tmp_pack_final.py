"""Empacota ZIP final com READMEatualizado."""
import sys, io, zipfile
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

dl = Path(r'C:\Users\gusta\Downloads')

readme = """\
ANALISE DE CORRELACAO — Carteira Inside Sales (Atualizada) x Sistema atual
Gerado: 25/05/2026 (apos reuniao Gustavo + Albert + Alves)

Fontes cruzadas:
  - PLANILHA: Carteira de Clientes - Inside Sales (Atualizado).xlsx
  - PLANILHA: Farmers Farmacias (version 1).xlsx (aba Ribeiro)
  - BASE BQ:  silver_comercial.param_com_rfv_carteira (clientes ativos)

Chave de cruzamento: ID ERP

================================================================
RESUMO EXECUTIVO
================================================================

CARTEIRA ATUAL (BQ):   1.112 clientes ativos
NOVA CARTEIRA TOTAL:   1.934 clientes (Hosp+SAC: 1.673 + Farmacia: 262)

Match (ID ERP bate):             1.016  (91,4% da carteira atual)
So na carteira atual:               96  (decidir: cliente novo OU inativo)
So na nova planilha:               982  (adicionar com vendedor da nova)

================================================================
QUEBRA DO MATCH (1.016 clientes)
================================================================

GANHA_DONO       214  Eram "Sem Vendedor" e agora ganham dono na nova planilha
                       129 -> Geovanna, 40 -> Kauan Ramos, 22 -> Kaua,
                       18 -> Guilherme, 5 -> Eduardo

rename_ok        541  So mudou o nome (mesmo vendedor):
                       Ramos -> Kauan Ramos (54)
                       Ribeiro -> Caua Ribeiro (247)
                       Eduardo -> Eduardo Marques (2)
                       Giovanna -> Geovanna Gomes (6)
                       Guilherme -> Guilherme Aquino (101)
                       Kaua -> Kaua Rodrigues (48)
                       Richard -> Richard Lucas (82)

TROCA_VENDEDOR   261  Cliente passa de uma pessoa pra OUTRA (revisar!):
                       Guilherme atual:  157 vao p/ outros (57 Richard, 39 Kauan, 38 Kaua,
                                         21 Eduardo, 2 Geovanna)
                       Kaua atual:       101 vao p/ outros (41 Richard, 34 Kauan, 20 Eduardo,
                                         4 Guilherme, 2 Geovanna)
                       Richard atual:      1 vai p/ Kauan Ramos
                       Giovanna atual:     2 vao p/ Kauan Ramos

================================================================
NOVOS PARA ADICIONAR (982 clientes da nova planilha)
================================================================

Richard Lucas:      254
Kauan Ramos:        219
Guilherme Aquino:   192
Kaua Rodrigues:     187
Geovanna Gomes:      83
Eduardo Marques:     33
Caua Ribeiro:        14

================================================================
ARQUIVOS NESTE ZIP
================================================================

1) carteira_conflito_vendedor.csv  (1.016 linhas — o mais importante)
   Todos os clientes do match com:
     - id_erp, partner_name, rfv_familia
     - vendedor_atual (sistema)
     - vendedor_nova (sua planilha)
     - status: GANHA_DONO | rename_ok | TROCA_VENDEDOR

   FILTRAR status='TROCA_VENDEDOR' para ver os 261 casos
   que precisam confirmacao tua.

2) carteira_nova_falta_adicionar.csv  (982 linhas)
   Clientes da sua planilha que ainda nao estao na carteira BQ.
   Serao inseridos com vendedor conforme planilha.

3) carteira_so_atual_nao_na_nova.csv  (96 linhas)
   Clientes da carteira atual que NAO aparecem na sua planilha.
   Decidir: descontinuados ou cliente novo a manter?

================================================================
APROVACAO PENDENTE
================================================================

Apos seu OK, vamos:
  - Substituir param_com_rfv_carteira pela nova base (1.934 clientes)
  - Renomear "Sem Vendedor" -> "Cliente Novo" no dashboard
  - Re-rodar RFV historico (Jan-Mai 2026) com nova carteira
  - Aplicar regra Giovanna so em SAC (se decidir manter)
"""

zip_path = dl / 'carteira_correlacao_25-05-2026.zip'
arquivos = [
    'carteira_conflito_vendedor.csv',
    'carteira_nova_falta_adicionar.csv',
    'carteira_so_atual_nao_na_nova.csv',
]
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    z.writestr('LEIA-ME.txt', readme)
    for arq in arquivos:
        p = dl / arq
        if p.exists():
            z.write(p, arq)
            print(f'  OK: {arq:50s} ({p.stat().st_size:>7,} bytes)')

print(f'\nZIP gerado: {zip_path}')
print(f'Tamanho final: {zip_path.stat().st_size:,} bytes')
