"""
Setup de dados de referência — Baixa lista oficial do IBGE.

Executar UMA VEZ antes de rodar o pipeline:
    python setup_reference_data.py

Baixa os municípios da API do IBGE e salva em:
    transform/reference_data/ibge_municipios.csv
"""

import json
import csv
import os
import sys
import urllib.request
import urllib.error
import gzip
from collections import Counter

IBGE_API_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transform", "reference_data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ibge_municipios.csv")


def download_ibge_municipios() -> list[dict]:
    """Baixa todos os municípios da API do IBGE."""
    print(f"Baixando municípios de: {IBGE_API_URL}")
    print("Aguarde...")

    req = urllib.request.Request(
        IBGE_API_URL,
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": "Mozilla/5.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw_bytes = response.read()
            content_encoding = response.headers.get("Content-Encoding", "").lower()

            if "gzip" in content_encoding:
                raw_bytes = gzip.decompress(raw_bytes)

            text = raw_bytes.decode("utf-8")
            data = json.loads(text)

            print(f"  ✓ {len(data)} municípios recebidos da API do IBGE")
            return data

    except urllib.error.URLError as e:
        print(f"  ✗ Erro ao acessar API do IBGE: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"  ✗ Erro ao interpretar JSON da API: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"  ✗ Erro inesperado no download/processamento: {e}")
        sys.exit(1)


def parse_municipios(raw_data: list[dict]) -> list[dict]:
    """Extrai campos relevantes e normaliza."""
    municipios = []

    for item in raw_data:
        municipios.append({
            "ibge_code": item.get("municipio-id", ""),
            "city_name": item.get("municipio-nome", "").strip().upper(),
            "state_code": item.get("UF-sigla", "").strip().upper(),
            "state_name": item.get("UF-nome", "").strip().upper(),
            "region": item.get("regiao-nome", "").strip().upper(),
        })

    return municipios


def save_csv(municipios: list[dict], filepath: str) -> None:
    """Salva como CSV."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["ibge_code", "city_name", "state_code", "state_name", "region"]
        )
        writer.writeheader()
        writer.writerows(municipios)

    print(f"  ✓ Salvo em: {filepath}")


def generate_stats(municipios: list[dict]) -> None:
    """Mostra estatísticas."""
    states = set(m["state_code"] for m in municipios)
    regions = set(m["region"] for m in municipios)

    print(f"\n  Estatísticas:")
    print(f"    Municípios: {len(municipios):,}")
    print(f"    Estados:    {len(states)}")
    print(f"    Regiões:    {len(regions)}")
    print(f"    Top 5 estados por qtd de municípios:")

    state_counts = Counter(m["state_code"] for m in municipios)
    for state, count in state_counts.most_common(5):
        print(f"      {state}: {count}")


def main():
    print("\n═══ Setup de Dados de Referência — IBGE ═══\n")

    if os.path.exists(OUTPUT_FILE):
        print(f"  ⚠ Arquivo já existe: {OUTPUT_FILE}")
        resp = input("  Deseja baixar novamente? (s/N): ").strip().lower()
        if resp != "s":
            print("  Mantendo arquivo existente.\n")
            return

    raw_data = download_ibge_municipios()
    municipios = parse_municipios(raw_data)
    save_csv(municipios, OUTPUT_FILE)
    generate_stats(municipios)

    print(f"\n  ✓ Setup concluído! Dados prontos em: {OUTPUT_FILE}")
    print("  Agora o pipeline pode usar fuzzy matching contra a lista oficial.\n")


if __name__ == "__main__":
    main()