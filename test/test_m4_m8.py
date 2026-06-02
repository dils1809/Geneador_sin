"""Tests M4 (FIRST/FOLLOW), M5 (LR0), M6 (tablas), M7 (paralelismo), M8 (parsers)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.yapar.spec_reader import Production
from src.yapar.first_follow import compute_first, compute_follow
from src.yapar.lr0 import LR0Automaton, Item
from src.yapar.tables import build_slr1_table, build_ll1_table
from src.yapar.parallel import ParallelParser
from src.parsers.mam_parser import parse_mam, tokenize_mam
from src.parsers.cow_parser import parse_cow
from src.parsers.messi_parser import parse_messi
from src.parsers.chocolat_parser import parse_chocolat


# ============== Gramatica de prueba: expr -> expr + term | term ==============
PRODS = [
    Production("expr", ["expr", "PLUS", "term"]),
    Production("expr", ["term"]),
    Production("term", ["LPAREN", "expr", "RPAREN"]),
    Production("term", ["ID"]),
]
TERMS = {"PLUS", "LPAREN", "RPAREN", "ID", "$"}


# ======================== M4: FIRST / FOLLOW ========================

def test_first_terminal_is_itself():
    first = compute_first(PRODS, TERMS)
    assert "ID" in first["ID"]

def test_first_of_term():
    first = compute_first(PRODS, TERMS)
    assert "LPAREN" in first["term"] and "ID" in first["term"]

def test_first_of_expr():
    first = compute_first(PRODS, TERMS)
    # expr puede empezar con LPAREN o ID (igual que term)
    assert "LPAREN" in first["expr"] and "ID" in first["expr"]

def test_follow_start_has_eof():
    first  = compute_first(PRODS, TERMS)
    follow = compute_follow(PRODS, "expr", first)
    assert "$" in follow["expr"]

def test_follow_term_has_plus():
    first  = compute_first(PRODS, TERMS)
    follow = compute_follow(PRODS, "expr", first)
    assert "PLUS" in follow["term"]

def test_follow_expr_has_rparen():
    first  = compute_first(PRODS, TERMS)
    follow = compute_follow(PRODS, "expr", first)
    assert "RPAREN" in follow["expr"]

def test_first_epsilon_grammar():
    # A -> B C, B -> epsilon, C -> 'x'
    prods = [Production("A",["B","C"]), Production("B",[]), Production("C",["x"])]
    first = compute_first(prods, {"x"})
    # FIRST(A) debe incluir 'x' porque B puede ser epsilon
    assert "x" in first["A"]


# ======================== M5: LR(0) ========================

def test_lr0_builds_states():
    lr0 = LR0Automaton(PRODS, "expr")
    assert len(lr0.states) > 0

def test_lr0_initial_state_not_empty():
    lr0 = LR0Automaton(PRODS, "expr")
    assert len(lr0.states[0].items) > 0

def test_lr0_has_transitions():
    lr0 = LR0Automaton(PRODS, "expr")
    all_transitions = sum(len(s.transitions) for s in lr0.states)
    assert all_transitions > 0

def test_lr0_items_have_dot():
    lr0 = LR0Automaton(PRODS, "expr")
    for state in lr0.states:
        for item in state.items:
            assert 0 <= item.dot <= len(item.body)

def test_lr0_detects_conflicts():
    # Gramatica ambigua genera conflictos
    ambig = [
        Production("S", ["S", "PLUS", "S"]),
        Production("S", ["ID"]),
    ]
    lr0 = LR0Automaton(ambig, "S")
    # Debe detectar conflictos shift/reduce
    assert len(lr0.conflicts) > 0


# ======================== M6: Tablas ========================

def test_slr1_action_not_empty():
    result = build_slr1_table(PRODS, list(TERMS - {"$"}), "expr")
    assert len(result["action"]) > 0

def test_slr1_goto_not_empty():
    result = build_slr1_table(PRODS, list(TERMS - {"$"}), "expr")
    assert len(result["goto"]) > 0

def test_slr1_has_accept():
    result = build_slr1_table(PRODS, list(TERMS - {"$"}), "expr")
    accepts = [v for v in result["action"].values() if v[0] == "accept"]
    assert len(accepts) > 0

def test_ll1_table_built():
    # Gramatica LL(1): expr -> term expr', expr' -> + term expr' | eps
    ll_prods = [
        Production("expr", ["term", "exprp"]),
        Production("exprp", ["PLUS", "term", "exprp"]),
        Production("exprp", []),
        Production("term", ["ID"]),
    ]
    result = build_ll1_table(ll_prods, ["PLUS","ID","$"], "expr")
    assert len(result["table"]) > 0


# ======================== M7: Paralelismo ========================

def test_parallel_parser_no_conflict():
    result = build_slr1_table(PRODS, list(TERMS - {"$"}), "expr")
    pp = ParallelParser(result["action"], result["goto"], PRODS)
    tokens = [("ID","x"), ("$","$")]
    r = pp.parse(tokens)
    assert r.success

def test_parallel_result_has_path():
    result = build_slr1_table(PRODS, list(TERMS - {"$"}), "expr")
    pp = ParallelParser(result["action"], result["goto"], PRODS)
    tokens = [("ID","x"), ("$","$")]
    r = pp.parse(tokens)
    assert r.winner in ("directo", "shift", "reduce", "ambos")


# ======================== M8: Parsers de aplicacion ========================

# -- Mam --
def test_mam_valid_simple():
    r = parse_mam("in jaw ixim .")
    assert r["valid"], r["error"]

def test_mam_valid_with_det():
    r = parse_mam("at tzaj tuj ja .")
    assert r["valid"], r["error"]

def test_mam_invalid_no_verb():
    r = parse_mam("in ixim .")
    assert not r["valid"]

def test_mam_invalid_unknown_word():
    r = parse_mam("hello world .")
    assert not r["valid"]

def test_mam_negation():
    r = parse_mam("mi e jaw ixim .")
    assert r["valid"], r["error"]

def test_mam_translation_exists():
    r = parse_mam("in jaw ixim .")
    assert r["valid"] and len(r["traduccion"]) > 0

def test_mam_tokenize_special_chars():
    # b'et y tz'ok tienen apostrofe
    tokens = tokenize_mam("at b'et tuj ja .")
    tipos = [t for t,_ in tokens]
    assert "VERBO" in tipos

# -- COW --
def test_cow_valid_simple():
    r = parse_cow("moO moO Moo")
    assert r["valid"], r["error"]

def test_cow_invalid_command():
    r = parse_cow("moo moo invalid")
    assert not r["valid"]

def test_cow_balanced_brackets():
    r = parse_cow("mOO MOo")
    assert r["valid"]

def test_cow_unbalanced_bracket():
    r = parse_cow("MOo")
    assert not r["valid"]

def test_cow_token_count():
    r = parse_cow("moo MOO mOo moO")
    assert r["valid"] and len(r["tokens"]) == 4

# -- MessiScript (sintaxis real del repo Erawaa) --
def test_messi_valid_simple():
    r = parse_messi("La agarra Messi. Va Messi, dando clases. Juega Messi. Le pega Messiiiii... gol!")
    assert r["valid"], r["error"]

def test_messi_valid_if_block():
    r = parse_messi("la agarra messi. sigue messi. juega messi. vuelve messi. le pega messi.")
    assert r["valid"], r["error"]

def test_messi_invalid_unclosed():
    r = parse_messi("la agarra messi. sigue messi. juega messi. le pega messi.")
    assert not r["valid"]

def test_messi_valid_while():
    r = parse_messi("La agarra Messi. La mueve Messi por la derecha. Siempre Messi. Juega Messi. Le pega Messi.")
    assert r["valid"]

# -- ChocolaT --
def test_chocolat_valid_minimal():
    r = parse_chocolat("cacao\n  siembra x = 1\nkakaw")
    assert r["valid"], r["error"]

def test_chocolat_valid_with_if():
    prog = "cacao\n  siembra x = 42\n  si_llueve x > 10\n    cosecha x\n  fin\nkakaw"
    r = parse_chocolat(prog)
    assert r["valid"], r["error"]

def test_chocolat_invalid_no_cacao():
    r = parse_chocolat("siembra x = 1\nkakaw")
    assert not r["valid"]

def test_chocolat_invalid_no_kakaw():
    r = parse_chocolat("cacao\n  siembra x = 1")
    assert not r["valid"]

def test_chocolat_unclosed_block():
    r = parse_chocolat("cacao\n  si_llueve verdad\n    cosecha x\nkakaw")
    assert not r["valid"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
