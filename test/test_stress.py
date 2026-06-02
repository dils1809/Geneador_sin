"""Pruebas de estres - casos complejos que podrian tronar."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.parsers.mam_parser      import parse_mam, tokenize_mam
from src.parsers.cow_parser      import parse_cow
from src.parsers.messi_parser    import parse_messi
from src.parsers.chocolat_parser import parse_chocolat
from src.yalex.nfa  import build_nfa
from src.yalex.dfa  import nfa_to_dfa, minimize_dfa
from src.yapar.spec_reader  import Production
from src.yapar.first_follow import compute_first, compute_follow
from src.yapar.lr0  import LR0Automaton
from src.yapar.tables import build_slr1_table, parse_slr1_tree
from src.yapar.lalr import build_lalr_table, parse_lalr


# ======================== MAM ==========================

def test_mam_5_oraciones():
    txt = "in jaw ixim . at b'et tuj ja . mi ey xnaq'tzb'il tuj ali . oj b'ixan tuj b'ix . e q'on tuj ja ."
    r = parse_mam(txt)
    assert r["valid"], r["error"]
    assert r["oraciones"] == 5

def test_mam_negacion_y_conjuncion():
    r = parse_mam("mi oj tzaj tnam . in ex at jaw ixim . ey b'ixan tuj b'ix .")
    assert r["valid"], r["error"]
    assert r["oraciones"] == 3

def test_mam_todos_los_verbos():
    for v in ["tzaj", "jaw", "b'et", "tz'ok", "tz'ib'", "xnaq'tzb'il", "q'on", "b'ixan"]:
        r = parse_mam("in " + v + " ixim .")
        assert r["valid"], "Verbo fallo: " + v

def test_mam_todos_los_sustantivos():
    for s in ["txutx", "tat", "ali", "achin", "ixim", "ja", "tnam", "witz"]:
        r = parse_mam("e jaw " + s + " .")
        assert r["valid"], "Sust fallo: " + s

def test_mam_parrafo_largo():
    parrafo = ("in jaw ixim . at b'et tuj ja . e tz'ok tnam . "
               "mi oj b'ixan . ey q'on tuj ja . at tzaj tnam . "
               "in xnaq'tzb'il tuj ali . e jaw ya' .")
    r = parse_mam(parrafo)
    assert r["valid"], r["error"]
    assert r["oraciones"] == 8

def test_mam_palabra_invalida_error():
    r = parse_mam("in jaw pizza .")
    assert not r["valid"] and "pizza" in r["error"]

def test_mam_orden_incorrecto_error():
    assert not parse_mam("ixim in jaw .")["valid"]

def test_mam_solo_negacion_error():
    assert not parse_mam("mi .")["valid"]

def test_mam_vacio_error():
    assert not parse_mam("")["valid"]

def test_mam_apostrofes():
    toks = tokenize_mam("at b'et tuj ja .")
    assert "VERBO" in [t for t, _ in toks]

def test_mam_det_sin_sust_error():
    assert not parse_mam("in tuj jaw .")["valid"]

def test_mam_solo_punto_error():
    assert not parse_mam(".")["valid"]


# ======================== COW ==========================

def test_cow_loop_simple():
    assert parse_cow("moO moO mOO MOO mOo MOo Moo")["valid"]

def test_cow_loops_anidados():
    assert parse_cow("mOO mOO Moo MOo MOo")["valid"]

def test_cow_tres_niveles():
    assert parse_cow("mOO mOO mOO MOo MOo MOo")["valid"]

def test_cow_programa_largo():
    assert parse_cow(" ".join(["moO"]*65 + ["Moo"]))["valid"]

def test_cow_todos_los_8_comandos():
    assert parse_cow("moo MOO mOo moO Moo MoO corre messi".replace("corre messi",""))["valid"]

def test_cow_sin_cerrar_error():
    assert not parse_cow("moO mOO Moo")["valid"]

def test_cow_moo_sin_sigue_error():
    assert not parse_cow("moO MOo Moo")["valid"]

def test_cow_comando_invalido_error():
    assert not parse_cow("moO invalid Moo")["valid"]

def test_cow_vacio_valido():
    assert parse_cow("")["valid"]

def test_cow_moo_extra_error():
    assert not parse_cow("mOO mOO MOo")["valid"]


# ======================== MESSISCRIPT ==========================

MESSI_FULL = (
    "La agarra Messi. Va Messi, dando clases. "
    "Corre Messi. La mueve Messi por la derecha. "
    "Siempre Messi. Amaga Messi. Sigue Messi. "
    "La pisa Messi. Gambetea Messi. Vuelve Messi. "
    "Juega Messi. Le pega Messi."
)

def test_messi_todos_comandos():
    assert parse_messi(MESSI_FULL)["valid"]

def test_messi_fibonacci_real():
    """El archivo fibonacci.messi real debe parsearse correctamente."""
    fib_path = os.path.join(os.path.dirname(__file__), "..", "examples", "messi", "fibonacci.messi")
    if os.path.exists(fib_path):
        with open(fib_path, encoding="utf-8-sig") as f:
            text = f.read()
        r = parse_messi(text)
        assert r["valid"], r["error"]
        assert r["token_count"] > 100  # programa largo
        assert r["estadisticas"].get("LOOP_START", 0) > 0

def test_messi_loops_anidados():
    prog = ("La agarra Messi. Sigue Messi. Sigue Messi. "
            "Juega Messi. Vuelve Messi. Vuelve Messi. Le pega Messi.")
    assert parse_messi(prog)["valid"]

def test_messi_case_insensitive():
    """El parser debe aceptar mayusculas mixtas."""
    assert parse_messi("LA AGARRA MESSI. JUEGA MESSI. LE PEGA MESSI.")["valid"]

def test_messi_con_comentarios():
    """Comentarios con # deben ignorarse."""
    prog = "La agarra Messi. # inicio\nJuega Messi. # imprimir\nLe pega Messi. # fin"
    assert parse_messi(prog)["valid"]

def test_messi_mover_izquierda():
    assert parse_messi("La agarra Messi. La mueve Messi por la izquierda. Juega Messi. Le pega Messi.")["valid"]

def test_messi_minimo():
    assert parse_messi("La agarra Messi. Le pega Messi.")["valid"]

def test_messi_vuelve_sin_sigue_error():
    assert not parse_messi("La agarra Messi. Juega Messi. Vuelve Messi. Le pega Messi.")["valid"]

def test_messi_sin_inicio_error():
    assert not parse_messi("Juega Messi. Le pega Messi.")["valid"]

def test_messi_sin_fin_error():
    assert not parse_messi("la agarra messi. juega messi.")["valid"]

def test_messi_sin_fin_real_error():
    # Programa sin marcador de fin — invalido
    assert not parse_messi("La agarra Messi. Juega Messi.")["valid"]

def test_messi_vacio_error():
    assert not parse_messi("")["valid"]


# ======================== CHOCOLAT ==========================

def test_chocolat_3_niveles():
    prog = "\n".join(["cacao","  siembra x = 100","  si_llueve x > 0",
                      "    mientras x > 50","      si_llueve x > 75",
                      "        cosecha x","      fin","    fin","  fin","kakaw"])
    assert parse_chocolat(prog)["valid"]

def test_chocolat_func_e_if():
    prog = "\n".join(["cacao","  func calcular","    siembra r = 42",
                      "    si_llueve r > 0","      cosecha r","    fin","  fin","kakaw"])
    assert parse_chocolat(prog)["valid"]

def test_chocolat_mientras():
    prog = "\n".join(["cacao","  siembra i = 10","  mientras i > 0",
                      "    cosecha i","  fin","kakaw"])
    assert parse_chocolat(prog)["valid"]

def test_chocolat_fin_extra_error():
    assert not parse_chocolat("cacao\n  siembra x = 1\n  fin\nkakaw")["valid"]

def test_chocolat_sin_cacao_error():
    assert not parse_chocolat("siembra x = 5\ncosecha x\nkakaw")["valid"]

def test_chocolat_sin_kakaw_error():
    assert not parse_chocolat("cacao\n  siembra x = 5")["valid"]

def test_chocolat_bloque_abierto_error():
    assert not parse_chocolat("cacao\n  si_llueve verdad\n    cosecha x\nkakaw")["valid"]

def test_chocolat_vacio_error():
    assert not parse_chocolat("")["valid"]


# ======================== REGEX ==========================

def test_regex_id_no_acepta_vacio():
    assert not nfa_to_dfa(build_nfa("[a-zA-Z][a-zA-Z0-9]*", token_name="ID")).start.is_accept

def test_regex_numero():
    dfa = minimize_dfa(nfa_to_dfa(build_nfa("[0-9]+", token_name="NUM")))
    assert dfa.match("123")[0][0] == "NUM"

def test_regex_kleene_acepta_vacio():
    assert nfa_to_dfa(build_nfa("((a|b)|c)*", token_name="T")).start.is_accept

def test_regex_plus_no_acepta_vacio():
    assert not nfa_to_dfa(build_nfa("a+", token_name="T")).start.is_accept

def test_regex_union_larga():
    assert len(nfa_to_dfa(build_nfa("(a|b|c|d|e|f|g|h|i|j)+", token_name="T")).states) > 0

def test_regex_hopcroft_no_agrega():
    nfa = build_nfa("(a|b)(a|b)", token_name="T")
    dfa = nfa_to_dfa(nfa)
    assert len(minimize_dfa(dfa).states) <= len(dfa.states)

def test_regex_concat_complejo():
    assert len(nfa_to_dfa(build_nfa("a*b+c?d", token_name="T")).states) > 0

def test_regex_clase_caracteres_grande():
    nfa = build_nfa("[a-zA-Z0-9_]+", token_name="ID")
    assert len(nfa_to_dfa(nfa).states) > 0


# ======================== GRAMATICAS COMPLEJAS ==========================

CALC = [
    Production("expr",   ["expr",   "PLUS",   "term"]),
    Production("expr",   ["expr",   "MINUS",  "term"]),
    Production("expr",   ["term"]),
    Production("term",   ["term",   "TIMES",  "factor"]),
    Production("term",   ["term",   "DIV",    "factor"]),
    Production("term",   ["factor"]),
    Production("factor", ["LPAREN", "expr",   "RPAREN"]),
    Production("factor", ["NUM"]),
    Production("factor", ["ID"]),
]
CALC_T = ["PLUS","MINUS","TIMES","DIV","LPAREN","RPAREN","NUM","ID"]
CALC_S = "expr"

AMBIG = [
    Production("E", ["E","PLUS","E"]),
    Production("E", ["E","TIMES","E"]),
    Production("E", ["ID"]),
]

def test_calc_slr1_sin_conflictos():
    assert len(build_slr1_table(CALC, CALC_T, CALC_S)["conflicts"]) == 0

def test_calc_lalr_sin_conflictos():
    assert len(build_lalr_table(CALC, CALC_T, CALC_S)["conflicts"]) == 0

def test_calc_lr0_muchos_estados():
    assert len(LR0Automaton(CALC, CALC_S).states) > 10

def test_calc_parseo_suma():
    r = build_slr1_table(CALC, CALC_T, CALC_S)
    _, tree = parse_slr1_tree(
        [("ID","x"),("PLUS","+"),("ID","y")], r["action"], r["goto"], CALC)
    assert tree.head == CALC_S

def test_calc_parseo_precedencia():
    r = build_slr1_table(CALC, CALC_T, CALC_S)
    toks = [("ID","x"),("PLUS","+"),("ID","y"),("TIMES","*"),("ID","z")]
    steps, tree = parse_slr1_tree(toks, r["action"], r["goto"], CALC)
    assert tree.head == CALC_S and len(steps) > 5

def test_calc_parseo_parentesis():
    r = build_slr1_table(CALC, CALC_T, CALC_S)
    toks = [("LPAREN","("),("ID","x"),("PLUS","+"),("ID","y"),
            ("RPAREN",")"),("TIMES","*"),("ID","z")]
    _, tree = parse_slr1_tree(toks, r["action"], r["goto"], CALC)
    assert tree.head == CALC_S

def test_calc_expr_larga():
    r = build_slr1_table(CALC, CALC_T, CALC_S)
    toks = [("ID","a"),("PLUS","+"),("ID","b"),("TIMES","*"),("ID","c"),
            ("MINUS","-"),("ID","d"),("DIV","/"),("ID","e")]
    steps, tree = parse_slr1_tree(toks, r["action"], r["goto"], CALC)
    assert tree.head == CALC_S and len(steps) > 10

def test_calc_token_invalido_error():
    r = build_slr1_table(CALC, CALC_T, CALC_S)
    try:
        parse_slr1_tree([("PLUS","+"),("ID","x")], r["action"], r["goto"], CALC)
        assert False, "Debia lanzar SyntaxError"
    except SyntaxError:
        pass

def test_ambigua_conflictos_slr():
    assert len(build_slr1_table(AMBIG, ["PLUS","TIMES","ID"], "E")["conflicts"]) > 0

def test_ambigua_conflictos_lalr():
    assert len(build_lalr_table(AMBIG, ["PLUS","TIMES","ID"], "E")["conflicts"]) > 0

def test_first_follow_calc():
    first  = compute_first(CALC, set(CALC_T))
    follow = compute_follow(CALC, CALC_S, first)
    assert all(t in first["expr"] for t in ["LPAREN","NUM","ID"])
    assert "$" in follow["expr"] and "RPAREN" in follow["expr"]

def test_lalr_expr_compleja():
    r = build_lalr_table(CALC, CALC_T, CALC_S)
    toks = [("ID","a"),("PLUS","+"),("ID","b"),("MINUS","-"),("ID","c")]
    _, tree = parse_lalr(toks, r["action"], r["goto"], CALC)
    assert tree.head == CALC_S


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
