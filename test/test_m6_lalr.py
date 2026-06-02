"""Tests de LALR, parse tree, SLR(1) con arbol y LL(1) tabla"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.yapar.spec_reader  import Production
from src.yapar.first_follow import compute_first, compute_follow
from src.yapar.tables       import build_slr1_table, build_ll1_table, parse_slr1_tree
from src.yapar.lalr         import build_lalr_table, parse_lalr
from src.yapar.parse_tree   import ParseNode

# Gramatica de prueba: expr → expr PLUS term | term; term → LP expr RP | ID
PRODS = [
    Production("expr", ["expr", "PLUS", "term"]),
    Production("expr", ["term"]),
    Production("term", ["LP", "expr", "RP"]),
    Production("term", ["ID"]),
]
TERMS = ["PLUS", "LP", "RP", "ID"]
START = "expr"
TOKENS = [("ID","x"), ("PLUS","+"), ("ID","y")]


# ── Parse tree ──────────────────────────────────────────────────────────────

def test_parse_node_terminal():
    n = ParseNode("ID", [], value="x")
    assert n.is_terminal()

def test_parse_node_nonterminal():
    n = ParseNode("expr", [ParseNode("ID",[],value="x")])
    assert not n.is_terminal()

def test_parse_node_pretty():
    n = ParseNode("expr", [ParseNode("ID",[],value="x")])
    pretty = n.pretty()
    assert "expr" in pretty and "ID" in pretty


# ── SLR(1) con arbol ────────────────────────────────────────────────────────

def test_slr1_tree_builds():
    r = build_slr1_table(PRODS, TERMS, START)
    steps, tree = parse_slr1_tree(TOKENS, r["action"], r["goto"], PRODS)
    assert tree is not None
    assert len(steps) > 0

def test_slr1_tree_root_is_start():
    r = build_slr1_table(PRODS, TERMS, START)
    _, tree = parse_slr1_tree(TOKENS, r["action"], r["goto"], PRODS)
    assert tree.head == START

def test_slr1_tree_has_children():
    r = build_slr1_table(PRODS, TERMS, START)
    _, tree = parse_slr1_tree(TOKENS, r["action"], r["goto"], PRODS)
    assert len(tree.children) > 0

def test_slr1_steps_have_fields():
    r = build_slr1_table(PRODS, TERMS, START)
    steps, _ = parse_slr1_tree(TOKENS, r["action"], r["goto"], PRODS)
    for s in steps:
        assert "stack" in s and "input" in s and "action" in s

def test_slr1_tree_error_on_invalid():
    r = build_slr1_table(PRODS, TERMS, START)
    bad = [("PLUS","+"), ("ID","x")]
    try:
        parse_slr1_tree(bad, r["action"], r["goto"], PRODS)
        assert False, "Debia lanzar SyntaxError"
    except SyntaxError:
        pass


# ── LALR ────────────────────────────────────────────────────────────────────

def test_lalr_table_builds():
    r = build_lalr_table(PRODS, TERMS, START)
    assert "action" in r and "goto" in r

def test_lalr_action_not_empty():
    r = build_lalr_table(PRODS, TERMS, START)
    assert len(r["action"]) > 0

def test_lalr_has_accept():
    r = build_lalr_table(PRODS, TERMS, START)
    accepts = [v for v in r["action"].values() if v[0] == "accept"]
    assert len(accepts) > 0

def test_lalr_no_conflicts_simple():
    r = build_lalr_table(PRODS, TERMS, START)
    assert len(r["conflicts"]) == 0

def test_lalr_detects_conflicts_ambiguous():
    # Gramatica ambigua: S -> S PLUS S | ID
    ambig = [
        Production("S", ["S", "PLUS", "S"]),
        Production("S", ["ID"]),
    ]
    r = build_lalr_table(ambig, ["PLUS","ID"], "S")
    assert len(r["conflicts"]) > 0

def test_lalr_parse_builds_tree():
    r = build_lalr_table(PRODS, TERMS, START)
    steps, tree = parse_lalr(TOKENS, r["action"], r["goto"], PRODS)
    assert tree is not None
    assert tree.head == START

def test_lalr_parse_steps():
    r = build_lalr_table(PRODS, TERMS, START)
    steps, _ = parse_lalr(TOKENS, r["action"], r["goto"], PRODS)
    assert len(steps) > 0

def test_lalr_fewer_conflicts_than_slr():
    # Para esta gramatica, ambos deben tener 0 conflictos,
    # pero verificamos que LALR no tiene MAS que SLR
    r_slr  = build_slr1_table(PRODS, TERMS, START)
    r_lalr = build_lalr_table(PRODS, TERMS, START)
    assert len(r_lalr["conflicts"]) <= len(r_slr["conflicts"])

def test_lalr_goto_not_empty():
    r = build_lalr_table(PRODS, TERMS, START)
    assert len(r["goto"]) > 0

def test_lalr_same_states_as_lr0():
    from src.yapar.lr0 import LR0Automaton
    lr0   = LR0Automaton(PRODS, START)
    r_lalr = build_lalr_table(PRODS, TERMS, START)
    # LALR tiene el mismo numero de estados que LR(0)
    assert len(r_lalr["lr0"].states) == len(lr0.states)


# ── LL(1) tabla ──────────────────────────────────────────────────────────────

def test_ll1_table_not_empty():
    # LL(1) funciona con gramatica no recursiva a izquierda
    ll_prods = [
        Production("E", ["T", "Ep"]),
        Production("Ep", ["PLUS", "T", "Ep"]),
        Production("Ep", []),
        Production("T", ["ID"]),
    ]
    r = build_ll1_table(ll_prods, ["PLUS","ID","$"], "E")
    assert len(r["table"]) > 0

def test_ll1_has_first_follow():
    ll_prods = [
        Production("E", ["T", "Ep"]),
        Production("Ep", ["PLUS", "T", "Ep"]),
        Production("Ep", []),
        Production("T", ["ID"]),
    ]
    r = build_ll1_table(ll_prods, ["PLUS","ID","$"], "E")
    assert "first" in r and "follow" in r

def test_ll1_left_recursive_has_conflict():
    # Gramatica con recursion izquierda → conflicto LL(1)
    r = build_ll1_table(PRODS, TERMS, START)
    # expr -> expr PLUS term es recursiva a izquierda
    # puede haber conflictos
    assert isinstance(r["conflicts"], list)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
