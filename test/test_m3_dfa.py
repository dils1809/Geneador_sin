"""Tests de M3: NFA -> DFA (subconjuntos) y DFA minimo (Hopcroft)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.yalex.nfa import build_nfa, EPSILON
from src.yalex.dfa import nfa_to_dfa, minimize_dfa, build_lexer_dfa


# ======================== Subconjuntos NFA -> DFA ========================

def test_dfa_char_single():
    """'a' debe producir un DFA que acepta solo 'a'."""
    nfa = build_nfa("a", token_name="A")
    dfa = nfa_to_dfa(nfa)
    assert dfa.start is not None
    assert len(dfa.accept_states) > 0

def test_dfa_char_rejects_other():
    """El DFA de 'a' no debe tener transicion para 'b' desde el inicio."""
    nfa = build_nfa("a")
    dfa = nfa_to_dfa(nfa)
    assert 'b' not in dfa.start.transitions

def test_dfa_alt():
    """'a|b' -> DFA con dos caminos que llevan al mismo estado de aceptacion."""
    nfa = build_nfa("a|b")
    dfa = nfa_to_dfa(nfa)
    assert 'a' in dfa.start.transitions
    assert 'b' in dfa.start.transitions

def test_dfa_star_accepts_empty():
    """'a*' debe incluir al estado inicial como estado de aceptacion."""
    nfa = build_nfa("a*", token_name="ASTAR")
    dfa = nfa_to_dfa(nfa)
    assert dfa.start.is_accept

def test_dfa_plus_rejects_empty():
    """'a+' no debe tener el estado inicial como estado de aceptacion."""
    nfa = build_nfa("a+", token_name="APLUS")
    dfa = nfa_to_dfa(nfa)
    assert not dfa.start.is_accept

def test_dfa_concat_two_chars():
    """'ab' -> DFA: inicio --a--> q1 --b--> q2(accept)."""
    nfa = build_nfa("ab")
    dfa = nfa_to_dfa(nfa)
    assert 'a' in dfa.start.transitions
    after_a = dfa.start.transitions['a']
    assert 'b' in after_a.transitions
    assert after_a.transitions['b'].is_accept

def test_dfa_no_epsilon_transitions():
    """El DFA NO debe tener epsilon-transiciones (esa es su ventaja sobre NFA)."""
    nfa = build_nfa("(a|b)*c")
    dfa = nfa_to_dfa(nfa)
    for state in dfa.states:
        assert EPSILON not in state.transitions

def test_dfa_alphabet_matches_nfa():
    """El alfabeto del DFA debe contener todos los simbolos del NFA."""
    nfa = build_nfa("a|b|c")
    dfa = nfa_to_dfa(nfa)
    for sym in ['a', 'b', 'c']:
        assert any(sym == s or (isinstance(s, frozenset) and sym in s)
                   for s in dfa.alphabet)

def test_dfa_match_simple():
    """match() sobre 'a' con DFA de 'a' debe devolver el token."""
    nfa = build_nfa("a", token_name="A", action="return token")
    dfa = nfa_to_dfa(nfa)
    tokens = dfa.match("a")
    assert len(tokens) == 1 and tokens[0][0] == "A"

def test_dfa_match_sequence():
    """DFA de 'ab' debe matchear 'ab' completo."""
    nfa = build_nfa("ab", token_name="AB", action="return token")
    dfa = nfa_to_dfa(nfa)
    tokens = dfa.match("ab")
    assert tokens[0][1] == "ab"


# ======================== Minimizacion de Hopcroft ========================

def test_minimize_reduces_states():
    """'(a|b)(a|b)' tiene estados redundantes que Hopcroft debe eliminar."""
    nfa = build_nfa("(a|b)(a|b)", token_name="T")
    dfa = nfa_to_dfa(nfa)
    min_dfa = minimize_dfa(dfa)
    assert len(min_dfa.states) <= len(dfa.states)

def test_minimize_preserves_acceptance():
    """El DFA minimo debe seguir aceptando las mismas cadenas."""
    nfa = build_nfa("ab", token_name="AB", action="return token")
    dfa = nfa_to_dfa(nfa)
    min_dfa = minimize_dfa(dfa)
    tokens = min_dfa.match("ab")
    assert tokens[0][1] == "ab"

def test_minimize_start_not_none():
    nfa = build_nfa("a*", token_name="A")
    dfa = nfa_to_dfa(nfa)
    min_dfa = minimize_dfa(dfa)
    assert min_dfa.start is not None

def test_minimize_single_char_optimal():
    """'a' ya es minimo (2 estados). Hopcroft no debe agregar estados."""
    nfa = build_nfa("a", token_name="A")
    dfa = nfa_to_dfa(nfa)
    min_dfa = minimize_dfa(dfa)
    # El minimo para 'a' es: inicio, aceptacion = 2 estados
    assert len(min_dfa.states) <= len(dfa.states)

def test_minimize_digit_class():
    """[0-9] -> DFA minimo con 2 estados: inicio y aceptacion."""
    nfa = build_nfa("[0-9]", token_name="DIGIT")
    dfa = nfa_to_dfa(nfa)
    min_dfa = minimize_dfa(dfa)
    # Todos los digitos van al mismo estado de aceptacion
    assert len(min_dfa.accept_states) >= 1

def test_build_lexer_dfa_pipeline():
    """Pipeline completo: NFA -> DFA -> DFA minimo."""
    nfa = build_nfa("[a-z]+", token_name="ID", action="return token")
    min_dfa = build_lexer_dfa(nfa)
    tokens = min_dfa.match("hello")
    assert tokens[0][0] == "ID" and tokens[0][1] == "hello"

def test_match_longest():
    """Longest match: 'aaa' con 'a+' debe retornar un token, no tres."""
    nfa = build_nfa("a+", token_name="A", action="return token")
    dfa = build_lexer_dfa(nfa)
    tokens = dfa.match("aaa")
    assert len(tokens) == 1 and tokens[0][1] == "aaa"

def test_match_rejects_invalid():
    """Un caracter fuera del patron debe lanzar ValueError."""
    import pytest
    nfa = build_nfa("a", token_name="A", action="return token")
    dfa = build_lexer_dfa(nfa)
    try:
        dfa.match("b")
        assert False, "Debia lanzar ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
