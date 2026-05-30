"""Tests de M1 (lectores .yal y .yapar) y M2 (regex -> NFA Thompson)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.yalex.spec_reader import load_yal, YalSpec, YalRule
from src.yapar.spec_reader import load_yapar, Production
from src.yalex.regex_parser import parse_regex, Char, Alt, Star, Concat, CharClass, Plus, Option, AnyChar
from src.yalex.nfa import build_nfa, EPSILON, ANY


# ===================== M1: YALex reader =====================

def test_yal_header():
    spec = load_yal("examples/simple.yal")
    assert "Lexer de calculadora" in spec.header

def test_yal_lets():
    spec = load_yal("examples/simple.yal")
    assert "digit" in spec.lets
    assert "letter" in spec.lets
    assert "ws" in spec.lets

def test_yal_entrypoint():
    spec = load_yal("examples/simple.yal")
    assert spec.entrypoint == "tokens"

def test_yal_rules_count():
    spec = load_yal("examples/simple.yal")
    assert len(spec.rules) >= 8  # NUM, ID, +, -, *, /, (, ), ws

def test_yal_first_rule_has_action():
    spec = load_yal("examples/simple.yal")
    assert spec.rules[0].action != ""

def test_yal_expand_lets():
    spec = load_yal("examples/simple.yal")
    expanded = spec.expand_lets("digit+")
    assert "digit" not in expanded  # reemplazado por el patron real

def test_yal_ws_action_empty():
    spec = load_yal("examples/simple.yal")
    ws_rules = [r for r in spec.rules if "ws" in r.pattern]
    assert any(r.action == "" for r in ws_rules)


# ===================== M1: YAPar reader =====================

def test_yapar_tokens():
    spec = load_yapar("examples/simple.yapar")
    assert "NUM" in spec.tokens
    assert "PLUS" in spec.tokens
    assert "RPAREN" in spec.tokens

def test_yapar_start_symbol():
    spec = load_yapar("examples/simple.yapar")
    assert spec.start_symbol == "expr"

def test_yapar_production_count():
    spec = load_yapar("examples/simple.yapar")
    # expr(3) + term(3) + factor(3) = 9
    assert len(spec.productions) == 9

def test_yapar_production_bodies():
    spec = load_yapar("examples/simple.yapar")
    heads = [p.head for p in spec.productions]
    assert "expr" in heads
    assert "term" in heads
    assert "factor" in heads


# ===================== M2: regex parser AST =====================

def test_parse_char():
    ast = parse_regex("a")
    assert isinstance(ast, Char) and ast.c == "a"

def test_parse_alt():
    ast = parse_regex("a|b")
    assert isinstance(ast, Alt)

def test_parse_star():
    ast = parse_regex("a*")
    assert isinstance(ast, Star)

def test_parse_plus():
    ast = parse_regex("a+")
    assert isinstance(ast, Plus)

def test_parse_option():
    ast = parse_regex("a?")
    assert isinstance(ast, Option)

def test_parse_concat():
    ast = parse_regex("ab")
    assert isinstance(ast, Concat)

def test_parse_char_class():
    ast = parse_regex("[a-z]")
    assert isinstance(ast, CharClass)
    assert 'a' in ast.chars and 'z' in ast.chars

def test_parse_any():
    ast = parse_regex(".")
    assert isinstance(ast, AnyChar)

def test_parse_nested():
    ast = parse_regex("(a|b)*c")
    assert isinstance(ast, Concat)


# ===================== M2: Thompson NFA =====================

def test_nfa_char_states():
    nfa = build_nfa("a")
    assert len(nfa.states) == 2
    assert nfa.start is not None
    assert nfa.accept.is_accept

def test_nfa_char_transition():
    nfa = build_nfa("a")
    syms = [s for s, _ in nfa.start.transitions]
    assert 'a' in syms

def test_nfa_alt_has_eps():
    nfa = build_nfa("a|b")
    eps_targets = [t for s, t in nfa.start.transitions if s is EPSILON]
    assert len(eps_targets) == 2

def test_nfa_star_skip():
    nfa = build_nfa("a*")
    # inicio debe tener eps directo al fin (cero repeticiones)
    eps_targets = [t for s, t in nfa.start.transitions if s is EPSILON]
    assert nfa.accept in eps_targets

def test_nfa_concat_accepts():
    nfa = build_nfa("ab")
    # simular: inicio -> 'a' -> eps -> 'b' -> accept
    after_a = [t for s, t in nfa.start.transitions if s == 'a']
    assert len(after_a) == 1
    mid = after_a[0]
    after_eps = [t for s, t in mid.transitions if s is EPSILON]
    assert len(after_eps) == 1

def test_epsilon_closure_trivial():
    nfa = build_nfa("a")
    closure = nfa.epsilon_closure([nfa.start])
    assert nfa.start in closure

def test_epsilon_closure_follows_eps():
    nfa = build_nfa("a*")
    closure = nfa.epsilon_closure([nfa.start])
    assert nfa.accept in closure  # start -eps-> accept para cero repeticiones

def test_move_char():
    nfa = build_nfa("a")
    after = nfa.move([nfa.start], 'a')
    assert nfa.accept in after

def test_move_no_match():
    nfa = build_nfa("a")
    after = nfa.move([nfa.start], 'b')
    assert len(after) == 0

def test_nfa_char_class():
    nfa = build_nfa("[0-9]")
    after = nfa.move([nfa.start], '5')
    assert len(after) == 1

def test_nfa_plus_at_least_one():
    nfa = build_nfa("a+")
    # inicio NO debe tener eps directo a accept (a diferencia de a*)
    eps_to_accept = [t for s, t in nfa.start.transitions if s is EPSILON and t == nfa.accept]
    assert len(eps_to_accept) == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
