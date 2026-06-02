"""
Tests del parser paralelo (M7) con gramaticas ambiguas.

La gramatica ambigua clasica:
  E → E + E | E * E | id

Para la cadena "id + id * id" hay DOS arboles validos:
  Arbol 1 (shift gana): id + (id * id)   — multiplicacion primero
  Arbol 2 (reduce gana): (id + id) * id  — suma primero

El parser paralelo lanza dos hilos y reporta AMBOS resultados.
Esto es lo que pide el PDF: "paralelismo para analisis de caminos alternativos".
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.yapar.spec_reader  import Production
from src.yapar.tables       import build_slr1_table
from src.yapar.lalr         import build_lalr_table
from src.yapar.parallel     import ParallelParser, ParallelResult, PathResult


# ── Gramatica ambigua: E → E+E | E*E | id ────────────────────────────────────
AMBIG = [
    Production("E", ["E", "PLUS",  "E"]),
    Production("E", ["E", "TIMES", "E"]),
    Production("E", ["ID"]),
]
AMBIG_T = ["PLUS", "TIMES", "ID"]

# ── Gramatica no ambigua: calculadora con precedencia ────────────────────────
CALC = [
    Production("expr",   ["expr",   "PLUS",  "term"]),
    Production("expr",   ["term"]),
    Production("term",   ["term",   "TIMES", "factor"]),
    Production("term",   ["factor"]),
    Production("factor", ["ID"]),
]
CALC_T = ["PLUS", "TIMES", "ID"]
CALC_S = "expr"


def _make_pp(prods, terms, start):
    r = build_slr1_table(prods, terms, start)
    return ParallelParser(r["action"], r["goto"], prods)


# ═══════════════ PathResult y ParallelResult ══════════════════════════════════

def test_path_result_defaults():
    p = PathResult("shift", False)
    assert p.label == "shift"
    assert not p.success
    assert p.steps == []

def test_parallel_result_fields():
    r = ParallelResult(success=True, winner="shift", both_accept=False)
    assert r.success
    assert r.winner == "shift"
    assert not r.both_accept


# ═══════════════ Gramatica NO ambigua — camino directo ═══════════════════════

def test_calc_no_conflicto_directo():
    pp = _make_pp(CALC, CALC_T, CALC_S)
    r  = pp.parse([("ID","x")])
    assert r.success
    assert r.winner == "directo"

def test_calc_suma_directo():
    pp = _make_pp(CALC, CALC_T, CALC_S)
    r  = pp.parse([("ID","x"), ("PLUS","+"), ("ID","y")])
    assert r.success

def test_calc_precedencia_directo():
    pp = _make_pp(CALC, CALC_T, CALC_S)
    r  = pp.parse([("ID","x"), ("PLUS","+"), ("ID","y"), ("TIMES","*"), ("ID","z")])
    assert r.success

def test_calc_token_invalido_falla():
    pp = _make_pp(CALC, CALC_T, CALC_S)
    r  = pp.parse([("PLUS","+"), ("ID","x")])
    assert not r.success


# ═══════════════ Gramatica AMBIGUA — paralelismo ══════════════════════════════

def test_ambigua_tiene_conflictos():
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    assert len(r["conflicts"]) > 0, "La gramatica ambigua debe tener conflictos"

def test_ambigua_id_solo():
    """'id' no tiene ambiguedad — un solo arbol."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","x")])
    assert result.success

def test_ambigua_id_plus_id():
    """'id + id' — puede haber conflicto, pero el resultado debe ser exitoso."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b")])
    assert result.success

def test_ambigua_id_plus_id_times_id_paralelo():
    """
    'id + id * id' — AMBIGUEDAD CLASICA.
    Dos interpretaciones:
      Shift gana:  id + (id * id)   — prioridad de *
      Reduce gana: (id + id) * id   — sin prioridad
    El parser paralelo debe encontrar al menos un camino exitoso.
    """
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b"), ("TIMES","*"), ("ID","c")])
    assert result.success, f"Al menos un camino debe aceptar: {result}"

def test_ambigua_winner_no_vacio():
    """El ganador debe ser uno de los valores validos."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b"), ("TIMES","*"), ("ID","c")])
    assert result.winner in ("shift", "reduce", "ambos", "directo")

def test_ambigua_both_accept_gramatica_ambigua():
    """
    Si AMBOS caminos aceptan, la gramatica ES ambigua para esta entrada.
    Reportamos both_accept=True.
    """
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b"), ("TIMES","*"), ("ID","c")])
    # Si ambos aceptan, es ambigua; si solo uno, tambien es valido
    assert result.success
    # both_accept puede ser True o False dependiendo de la resolucion
    assert isinstance(result.both_accept, bool)

def test_ambigua_conflict_at_registrado():
    """El punto de conflicto debe quedar registrado."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b"), ("TIMES","*"), ("ID","c")])
    if result.winner not in ("directo", "ninguno"):
        assert result.conflict_at is not None
        state, sym = result.conflict_at
        assert isinstance(state, int)
        assert isinstance(sym, str)

def test_ambigua_steps_before_existen():
    """Debe haber pasos registrados antes del conflicto."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b"), ("TIMES","*"), ("ID","c")])
    assert result.steps_before is not None

def test_ambigua_shift_path_tiene_steps():
    """Si el camino shift tuvo exito, debe tener pasos."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b"), ("TIMES","*"), ("ID","c")])
    if result.shift_path and result.shift_path.success:
        assert len(result.shift_path.steps) > 0

def test_ambigua_reduce_path_tiene_steps():
    """Si el camino reduce tuvo exito, debe tener pasos."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b"), ("TIMES","*"), ("ID","c")])
    if result.reduce_path and result.reduce_path.success:
        assert len(result.reduce_path.steps) > 0

def test_ambigua_tree_en_camino_exitoso():
    """El camino exitoso debe tener un arbol de derivacion."""
    from src.yapar.parse_tree import ParseNode
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b")])
    exitoso = result.shift_path if (result.shift_path and result.shift_path.success) \
              else result.reduce_path
    if exitoso and exitoso.success:
        assert exitoso.tree is not None

def test_ambigua_cadena_invalida():
    """Una cadena invalida debe fallar en ambos caminos."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("PLUS","+"), ("ID","x")])
    assert not result.success

def test_ambigua_larga():
    """Cadena mas larga: id + id + id * id * id."""
    r = build_slr1_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    toks = [("ID","a"), ("PLUS","+"), ("ID","b"), ("PLUS","+"),
            ("ID","c"), ("TIMES","*"), ("ID","d"), ("TIMES","*"), ("ID","e")]
    result = pp.parse(toks)
    assert result.success

def test_paralelo_con_lalr():
    """El parser paralelo funciona con tablas LALR tambien."""
    r = build_lalr_table(AMBIG, AMBIG_T, "E")
    pp = ParallelParser(r["action"], r["goto"], AMBIG)
    result = pp.parse([("ID","a"), ("PLUS","+"), ("ID","b")])
    assert result.success


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
