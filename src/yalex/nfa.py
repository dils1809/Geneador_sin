"""
M2 - Construccion de NFA por el algoritmo de Thompson

Algoritmo de Thompson: cada operador de la regex genera un fragmento NFA
con exactamente UN estado inicial y UN estado de aceptacion.
Los fragmentos se conectan con epsilon-transiciones.

Los 6 casos:
  Char(c)    -> (s0) --c--> ((s1))
  AnyChar()  -> (s0) --ANY--> ((s1))
  CharClass  -> (s0) --{chars}--> ((s1))
  Concat(a,b)-> frag_a.end --eps--> frag_b.start
  Alt(a,b)   -> nuevo_inicio --eps--> frag_a.start
                             --eps--> frag_b.start
               frag_a.end   --eps--> nuevo_fin
               frag_b.end   --eps--> nuevo_fin
  Star(a)    -> nuevo_inicio --eps--> frag_a.start  (puede saltarse)
               frag_a.end   --eps--> frag_a.start  (ciclo)
               frag_a.end   --eps--> nuevo_fin
               nuevo_inicio --eps--> nuevo_fin      (cero veces)
  Plus(a)    -> igual que Star pero sin el salto directo inicio->fin
  Option(a)  -> igual que Alt(a, Epsilon)

Complejidad: O(n) estados y transiciones donde n = longitud del patron.
"""

from dataclasses import dataclass, field
from typing import Optional
from .regex_parser import (
    parse_regex, Char, AnyChar, CharClass, Concat, Alt, Star, Plus, Option, Epsilon
)

EPSILON = None   # usamos None como simbolo de epsilon-transicion
ANY     = "ANY"  # simbolo especial para punto (cualquier caracter)


@dataclass
class State:
    id: int
    is_accept: bool = False
    # transitions: lista de (simbolo, estado_destino)
    # simbolo puede ser: str (un char), frozenset (clase), EPSILON (None), ANY
    transitions: list = field(default_factory=list)

    def add(self, symbol, target):
        self.transitions.append((symbol, target))

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, State) and self.id == other.id

    def __repr__(self):
        acc = "*" if self.is_accept else ""
        return f"q{self.id}{acc}"


class NFA:
    def __init__(self):
        self._counter = 0
        self.states: list[State] = []
        self.start: Optional[State] = None
        self.accept: Optional[State] = None

    def new_state(self) -> State:
        s = State(id=self._counter)
        self._counter += 1
        self.states.append(s)
        return s

    # --- epsilon-closure y move (necesarios para M3) ---

    def epsilon_closure(self, states) -> frozenset:
        """Todos los estados alcanzables desde 'states' usando solo epsilon."""
        closure = set(states)
        stack = list(states)
        while stack:
            s = stack.pop()
            for sym, target in s.transitions:
                if sym is EPSILON and target not in closure:
                    closure.add(target)
                    stack.append(target)
        return frozenset(closure)

    def move(self, states, symbol: str) -> frozenset:
        """Estados alcanzables desde 'states' consumiendo 'symbol' (sin epsilon)."""
        result = set()
        for s in states:
            for sym, target in s.transitions:
                if sym is EPSILON:
                    continue
                if sym == ANY:
                    result.add(target)
                elif isinstance(sym, frozenset) and symbol in sym:
                    result.add(target)
                elif sym == symbol:
                    result.add(target)
        return frozenset(result)


# --- Constructor de Thompson ---

def build_nfa(pattern: str, token_name: str = "", action: str = "") -> NFA:
    """Construye un NFA desde un string de patron regex."""
    ast = parse_regex(pattern)
    nfa = NFA()
    start, end = _build(ast, nfa)
    end.is_accept = True
    end.token_name = token_name
    end.action = action
    nfa.start = start
    nfa.accept = end
    return nfa


def _build(node, nfa: NFA):
    """Devuelve (estado_inicial, estado_final) del fragmento NFA para 'node'."""

    if isinstance(node, Epsilon):
        s0 = nfa.new_state()
        s1 = nfa.new_state()
        s0.add(EPSILON, s1)
        return s0, s1

    if isinstance(node, Char):
        s0 = nfa.new_state()
        s1 = nfa.new_state()
        s0.add(node.c, s1)
        return s0, s1

    if isinstance(node, AnyChar):
        s0 = nfa.new_state()
        s1 = nfa.new_state()
        s0.add(ANY, s1)
        return s0, s1

    if isinstance(node, CharClass):
        s0 = nfa.new_state()
        s1 = nfa.new_state()
        s0.add(node.chars, s1)
        return s0, s1

    if isinstance(node, Concat):
        ls, le = _build(node.left, nfa)
        rs, re_ = _build(node.right, nfa)
        le.add(EPSILON, rs)
        return ls, re_

    if isinstance(node, Alt):
        s0 = nfa.new_state()
        s1 = nfa.new_state()
        ls, le = _build(node.left, nfa)
        rs, re_ = _build(node.right, nfa)
        s0.add(EPSILON, ls)
        s0.add(EPSILON, rs)
        le.add(EPSILON, s1)
        re_.add(EPSILON, s1)
        return s0, s1

    if isinstance(node, Star):
        s0 = nfa.new_state()
        s1 = nfa.new_state()
        es, ee = _build(node.expr, nfa)
        s0.add(EPSILON, es)
        s0.add(EPSILON, s1)
        ee.add(EPSILON, es)
        ee.add(EPSILON, s1)
        return s0, s1

    if isinstance(node, Plus):
        # a+ = aa*
        es, ee = _build(node.expr, nfa)
        s1 = nfa.new_state()
        ee.add(EPSILON, es)  # ciclo
        ee.add(EPSILON, s1)
        return es, s1

    if isinstance(node, Option):
        s0 = nfa.new_state()
        s1 = nfa.new_state()
        es, ee = _build(node.expr, nfa)
        s0.add(EPSILON, es)
        s0.add(EPSILON, s1)
        ee.add(EPSILON, s1)
        return s0, s1

    raise ValueError(f"Nodo desconocido: {type(node)}")
