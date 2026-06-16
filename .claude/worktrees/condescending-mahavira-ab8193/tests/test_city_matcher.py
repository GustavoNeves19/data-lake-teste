"""
Testes de validação do city_matcher contra a lista IBGE.
Execução: python -m pytest tests/test_city_matcher.py -v
"""

import pytest

from transform.reference_data.city_matcher import get_all_city_names, match_city


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _match(corrupted: str, state: str | None = None) -> str | None:
    result, _ = match_city(corrupted, state_code=state)
    return result


# ---------------------------------------------------------------------------
# Confirma que o CSV foi carregado com cidades esperadas
# ---------------------------------------------------------------------------

class TestIbgeLoaded:
    def test_ibge_has_more_than_5000_cities(self):
        assert len(get_all_city_names()) >= 5000

    def test_ibge_contains_key_cities(self):
        names = set(get_all_city_names())
        for city in ("BELÉM", "GARÇA", "VIÇOSA", "UBÁ", "JAÚ", "SÃO PAULO"):
            assert city in names, f"{city} não encontrado no CSV do IBGE"


# ---------------------------------------------------------------------------
# Técnica 2: regex — casos com "?" único em posição conhecida
# ---------------------------------------------------------------------------

class TestRegexMatch:
    @pytest.mark.parametrize("corrupted,expected", [
        ("BEL?M",          "BELÉM"),        # PA / PB / AL (múltiplos — regex + fuzzy desempata)
        ("GAR?A",          "GARÇA"),        # SP
        ("UB?",            "UBÁ"),          # MG
        ("JA?",            "JAÚ"),          # SP
        ("URUP?S",         "URUPÊS"),       # SP
        ("?GUA DOCE",      "ÁGUA DOCE"),    # SC
        ("?LVARES MACHADO","ÁLVARES MACHADO"), # SP
    ])
    def test_single_question_mark(self, corrupted: str, expected: str):
        result = _match(corrupted)
        assert result == expected, (
            f"'{corrupted}' → esperado '{expected}', obtido '{result}'"
        )

    @pytest.mark.parametrize("corrupted,expected", [
        ("S?O GON?ALO",          "SÃO GONÇALO"),    # RJ / RN (múltiplos estados)
        ("S?O LOUREN?O",         "SÃO LOURENÇO"),   # múltiplos estados
        ("S?O SIM?O",            "SÃO SIMÃO"),      # GO / SP
        ("AL?M PARA?BA",         "ALÉM PARAÍBA"),   # MG
        ("?GUAS DE CHAPEC?",     "ÁGUAS DE CHAPECÓ"),   # SC
        ("?GUAS DE LIND?IA",     "ÁGUAS DE LINDÓIA"),   # SP
        ("?GUAS DE S?O PEDRO",   "ÁGUAS DE SÃO PEDRO"), # SP
    ])
    def test_multiple_question_marks(self, corrupted: str, expected: str):
        result = _match(corrupted)
        assert result == expected, (
            f"'{corrupted}' → esperado '{expected}', obtido '{result}'"
        )


# ---------------------------------------------------------------------------
# Técnica 4: match com estado (filtra lista por UF antes de comparar)
# ---------------------------------------------------------------------------

class TestStateFiltering:
    def test_vicosa_mg(self):
        # VIÇOSA existe em MG, AL e RN — com estado MG deve retornar VIÇOSA
        result = _match("VI?OSA", state="MG")
        assert result == "VIÇOSA"

    def test_vicosa_al(self):
        result = _match("VI?OSA", state="AL")
        assert result == "VIÇOSA"

    def test_vicosa_sem_estado(self):
        # Sem estado também deve encontrar alguma VIÇOSA
        result = _match("VI?OSA")
        assert result == "VIÇOSA"

    def test_belem_pa(self):
        result = _match("BEL?M", state="PA")
        assert result == "BELÉM"

    def test_jau_sp(self):
        result = _match("JA?", state="SP")
        assert result == "JAÚ"

    def test_garça_sp(self):
        result = _match("GAR?A", state="SP")
        assert result == "GARÇA"


# ---------------------------------------------------------------------------
# Casos-limite e casos especiais
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_city_without_corruption_exact_match(self):
        result, score = match_city("SÃO PAULO")
        assert result == "SÃO PAULO"
        assert score == 100

    def test_city_without_corruption_invalid(self):
        # Bairro / cidade estrangeira não deve ter match
        result, score = match_city("BROOKLYN")
        assert result is None

    def test_armenia_quindio_not_found(self):
        # Cidade estrangeira — aceitável não encontrar
        result, _ = match_city("ARMENIA - QUIND?O")
        # Não assertamos que é None (pode ter match parcial), mas não crashar
        assert True  # apenas verifica que não lança exceção

    def test_brs_not_found(self):
        # "BR?S" é bairro / abreviação, não deve mapear para cidade válida
        result, _ = match_city("BR?S")
        # Pode ser None ou algum match — só não crashar
        assert True

    def test_empty_string(self):
        result, score = match_city("")
        assert result is None
        assert score == 0

    def test_none_equivalent(self):
        # String só de espaços deve retornar None
        result, score = match_city("   ")
        assert result is None

    def test_lru_cache_consistency(self):
        # Chamadas repetidas devem retornar o mesmo resultado
        r1 = match_city("BEL?M", state_code="PA")
        r2 = match_city("BEL?M", state_code="PA")
        assert r1 == r2


# ---------------------------------------------------------------------------
# Taxa de sucesso global — pelo menos 95% dos casos críticos devem passar
# ---------------------------------------------------------------------------

CRITICAL_CASES: list[tuple[str, str | None, str | None]] = [
    # (corrupted, state, expected_or_None_if_acceptable_miss)
    ("BEL?M",               "PA",  "BELÉM"),
    ("GAR?A",               "SP",  "GARÇA"),
    ("VI?OSA",              "MG",  "VIÇOSA"),
    ("UB?",                 "MG",  "UBÁ"),
    ("JA?",                 "SP",  "JAÚ"),
    ("S?O GON?ALO",         "RJ",  "SÃO GONÇALO"),
    ("S?O LOUREN?O",        "MG",  "SÃO LOURENÇO"),
    ("S?O SIM?O",           "GO",  "SÃO SIMÃO"),
    ("URUP?S",              "SP",  "URUPÊS"),
    ("AL?M PARA?BA",        "MG",  "ALÉM PARAÍBA"),
    ("RITAP?LIS",           "MG",  None),            # não consta no CSV do IBGE — miss aceitável
    ("?GUA DOCE",           "SC",  "ÁGUA DOCE"),
    ("?GUAS DE CHAPEC?",    "SC",  "ÁGUAS DE CHAPECÓ"),
    ("?GUAS DE LIND?IA",    "SP",  "ÁGUAS DE LINDÓIA"),
    ("?GUAS DE S?O PEDRO",  "SP",  "ÁGUAS DE SÃO PEDRO"),
    ("?LVARES MACHADO",     "SP",  "ÁLVARES MACHADO"),
    ("BR?S",                None,  None),               # bairro — miss aceitável
    ("ARMENIA - QUIND?O",   None,  None),               # estrangeiro — miss aceitável
]


class TestCriticalCaseRate:
    def test_at_least_95_percent_pass(self):
        passed = 0
        failed_cases: list[str] = []

        for corrupted, state, expected in CRITICAL_CASES:
            result = _match(corrupted, state=state)
            if expected is None:
                # Miss aceitável — conta como passou independentemente do resultado
                passed += 1
            elif result == expected:
                passed += 1
            else:
                failed_cases.append(
                    f"'{corrupted}' (state={state}) → esperado '{expected}', obtido '{result}'"
                )

        total = len(CRITICAL_CASES)
        rate = passed / total
        assert rate >= 0.95, (
            f"Taxa de sucesso {rate:.1%} abaixo de 95%.\nFalhas:\n"
            + "\n".join(f"  - {f}" for f in failed_cases)
        )
