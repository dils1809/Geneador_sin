"""
M3 - YALex: pipeline completo .yal -> tokens

Une todos los modulos anteriores:
  1. load_yal()     -> YalSpec (M1)
  2. expand_lets()  -> patron expandido (M1)
  3. parse_regex()  -> AST (M2)
  4. build_nfa()    -> NFA por Thompson (M2)
  5. nfa_to_dfa()   -> DFA por subconjuntos (M3)
  6. minimize_dfa() -> DFA minimo por Hopcroft (M3)

El lexer generado soporta "longest match" (maximal munch):
  cuando hay ambiguedad, gana el match mas largo.
  Si dos patrones tienen la misma longitud, gana el que aparece primero en el .yal.

Para combinar multiples patrones (uno por regla del .yal) se construye
un NFA combinado con un nuevo estado inicial que tiene eps-transiciones
a cada NFA individual. Esto permite reconocer cualquiera de los patrones
con una sola pasada del DFA.
"""

from .spec_reader import load_yal, YalSpec
from .regex_parser import parse_regex
from .nfa import build_nfa, NFA, EPSILON
from .dfa import nfa_to_dfa, minimize_dfa, DFA, DfaState


class Lexer:
    def __init__(self, dfa: DFA):
        self.dfa = dfa

    def tokenize(self, text: str) -> list:
        """
        Aplica longest match sobre 'text'.
        Devuelve lista de (token_name, lexema).
        Las acciones vacias (whitespace) se omiten del resultado.
        """
        return self.dfa.match(text)


def build_lexer_from_spec(spec: YalSpec) -> Lexer:
    """
    Construye un Lexer desde un YalSpec ya cargado.
    Combina todos los patrones en un solo NFA antes de convertir a DFA.
    """
    combined = _combine_nfas(spec)
    dfa = nfa_to_dfa(combined)
    min_dfa = minimize_dfa(dfa)
    return Lexer(min_dfa)


def build_lexer_from_file(path: str) -> Lexer:
    """Atajo: ruta al .yal -> Lexer listo para usar."""
    spec = load_yal(path)
    return build_lexer_from_spec(spec)


def _combine_nfas(spec: YalSpec) -> NFA:
    """
    Crea un NFA combinado con un nuevo estado inicial que tiene
    epsilon-transiciones a cada NFA de cada regla del .yal.
    La prioridad se maneja por orden: el estado de aceptacion del NFA
    con menor indice tiene prioridad en caso de conflicto.
    """
    combined = NFA()
    new_start = combined.new_state()

    for i, rule in enumerate(spec.rules):
        expanded = spec.expand_lets(rule.pattern)
        try:
            nfa = build_nfa(expanded, token_name=f"rule_{i}", action=rule.action)
        except Exception:
            # patron que no se puede parsear todavia -> skip
            continue
        # Transferir estados al NFA combinado
        for state in nfa.states:
            state.id += combined._counter
            combined.states.append(state)
        combined._counter += sum(1 for _ in nfa.states)
        nfa.accept.is_accept = True
        nfa.accept.token_name = _infer_token_name(rule)
        nfa.accept.action = rule.action
        new_start.add(EPSILON, nfa.start)

    combined.start = new_start
    return combined


def _infer_token_name(rule) -> str:
    """Extrae el nombre del token de la accion (ej: return ("NUM", ...) -> NUM)."""
    import re
    m = re.search(r'return\s*\(\s*["\'](\w+)["\']', rule.action)
    if m:
        return m.group(1)
    return ""
