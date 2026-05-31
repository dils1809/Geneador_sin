"""
M3 - Construccion de DFA por subconjuntos y minimizacion por Hopcroft

PARTE A: NFA -> DFA (algoritmo de subconjuntos)
  Idea central: un estado del DFA ES un conjunto de estados del NFA.
  Arrancamos con epsilon_closure({nfa.start}) como estado inicial del DFA.
  Por cada simbolo del alfabeto, calculamos move() + epsilon_closure() para
  obtener el siguiente estado DFA. Repetimos hasta que no haya estados nuevos.

  Complejidad: O(2^n) estados en el peor caso, O(n * |alfabeto|) transiciones.
  Punto critico: si el NFA tiene n estados, el DFA puede tener hasta 2^n.
  En la practica con patrones de lenguajes reales es mucho menor.

PARTE B: DFA minimo (algoritmo de Hopcroft)
  Idea central: particion de estados en clases de equivalencia.
  Dos estados son equivalentes si para todo simbolo van a la misma clase.
  Empezamos con dos grupos: {estados de aceptacion} y {el resto}.
  Refinamos iterativamente hasta que la particion no cambie.

  Complejidad: O(n * |alfabeto| * log n) donde n = estados del DFA.
  Resultado: el DFA con el MINIMO numero posible de estados.
"""

from dataclasses import dataclass, field
from .nfa import NFA, EPSILON, ANY, State as NfaState


# ---------------------------------------------------------------------------
# Estructuras del DFA
# ---------------------------------------------------------------------------

@dataclass
class DfaState:
    id: int
    nfa_states: frozenset        # conjunto de estados NFA que representa
    is_accept: bool = False
    token_name: str = ""         # nombre del token si es estado de aceptacion
    action: str = ""             # accion asociada
    transitions: dict = field(default_factory=dict)  # simbolo -> DfaState

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, DfaState) and self.id == other.id

    def __repr__(self):
        acc = "*" if self.is_accept else ""
        return f"D{self.id}{acc}({self.token_name})"


@dataclass
class DFA:
    states: list = field(default_factory=list)
    start: DfaState = None
    accept_states: list = field(default_factory=list)
    alphabet: frozenset = field(default_factory=frozenset)

    def match(self, text: str):
        """
        Simula el DFA sobre 'text'.
        Devuelve lista de (token_name, lexema) o lanza ValueError si falla.
        Implementa el principio de longest match (maximal munch).
        """
        tokens = []
        pos = 0
        while pos < len(text):
            state = self.start
            last_accept = None
            last_pos = pos
            i = pos
            while i < len(text):
                ch = text[i]
                sym = self._resolve_symbol(state, ch)
                if sym is None or sym not in state.transitions:
                    break
                state = state.transitions[sym]
                i += 1
                if state.is_accept:
                    last_accept = state
                    last_pos = i
            if last_accept is None:
                raise ValueError(
                    f"Error lexico en posicion {pos}: caracter inesperado '{text[pos]}'"
                )
            lexema = text[pos:last_pos]
            # Emitir token si tiene nombre o accion (accion vacia = skip, ej whitespace)
            if last_accept.token_name or last_accept.action:
                tokens.append((last_accept.token_name, lexema))
            pos = last_pos
        return tokens

    def _resolve_symbol(self, state: DfaState, ch: str):
        """Encuentra el simbolo en las transiciones que hace match con ch."""
        if ch in state.transitions:
            return ch
        for sym in state.transitions:
            if isinstance(sym, frozenset) and ch in sym:
                return sym
            if sym == ANY:
                return ANY
        return None


# ---------------------------------------------------------------------------
# PARTE A: Algoritmo de subconjuntos NFA -> DFA
# ---------------------------------------------------------------------------

def nfa_to_dfa(nfa: NFA) -> DFA:
    """Convierte un NFA en un DFA equivalente usando subconjuntos."""
    alphabet = _extract_alphabet(nfa)
    dfa = DFA(alphabet=alphabet)
    counter = [0]

    def new_dfa_state(nfa_set: frozenset) -> DfaState:
        is_acc, tok, act = _accept_info(nfa_set)
        ds = DfaState(
            id=counter[0],
            nfa_states=nfa_set,
            is_accept=is_acc,
            token_name=tok,
            action=act,
        )
        counter[0] += 1
        dfa.states.append(ds)
        if is_acc:
            dfa.accept_states.append(ds)
        return ds

    start_set = nfa.epsilon_closure([nfa.start])
    start_state = new_dfa_state(start_set)
    dfa.start = start_state

    # mapa: frozenset(nfa_states) -> DfaState (para no duplicar)
    mapping = {start_set: start_state}
    worklist = [start_state]

    while worklist:
        ds = worklist.pop()
        for sym in alphabet:
            moved = nfa.move(ds.nfa_states, sym)
            if not moved:
                continue
            closed = nfa.epsilon_closure(moved)
            if not closed:
                continue
            if closed not in mapping:
                new_ds = new_dfa_state(closed)
                mapping[closed] = new_ds
                worklist.append(new_ds)
            ds.transitions[sym] = mapping[closed]

    return dfa


def _extract_alphabet(nfa: NFA) -> frozenset:
    """Recolecta todos los simbolos usados en el NFA (sin epsilon)."""
    symbols = set()
    for state in nfa.states:
        for sym, _ in state.transitions:
            if sym is not EPSILON:
                symbols.add(sym)
    return frozenset(symbols)


def _accept_info(nfa_states: frozenset):
    """Si alguno de los estados NFA es de aceptacion, devuelve su info."""
    for s in nfa_states:
        if s.is_accept:
            return True, getattr(s, 'token_name', ''), getattr(s, 'action', '')
    return False, '', ''


# ---------------------------------------------------------------------------
# PARTE B: Minimizacion de Hopcroft
# ---------------------------------------------------------------------------

def minimize_dfa(dfa: DFA) -> DFA:
    """
    Aplica el algoritmo de Hopcroft para obtener el DFA minimo.
    Devuelve un DFA nuevo con el minimo numero de estados.
    """
    if not dfa.states:
        return dfa

    # Paso 1: particion inicial — aceptacion vs no-aceptacion
    accept_ids = frozenset(s.id for s in dfa.accept_states)
    non_accept_ids = frozenset(s.id for s in dfa.states if s.id not in accept_ids)

    partitions = []
    if accept_ids:
        partitions.append(accept_ids)
    if non_accept_ids:
        partitions.append(non_accept_ids)

    # Para localizar rapidamente a que particion pertenece cada estado
    def find_group(state_id, parts):
        for i, part in enumerate(parts):
            if state_id in part:
                return i
        return -1

    # Paso 2: refinar particiones
    changed = True
    while changed:
        changed = False
        new_parts = []
        for group in partitions:
            splits = _split_group(group, partitions, dfa, find_group)
            new_parts.extend(splits)
            if len(splits) > 1:
                changed = True
        partitions = new_parts

    # Paso 3: construir DFA minimo
    return _build_minimal_dfa(dfa, partitions, find_group)


def _split_group(group: frozenset, partitions, dfa: DFA, find_group):
    """
    Intenta dividir 'group' en subgrupos donde todos los estados
    van al mismo grupo para cada simbolo del alfabeto.
    """
    state_map = {s.id: s for s in dfa.states}
    group_list = list(group)
    if len(group_list) == 1:
        return [group]

    # Firma de un estado: tupla (grupo_destino por cada simbolo)
    def signature(state_id):
        s = state_map[state_id]
        sig = {}
        for sym in dfa.alphabet:
            if sym in s.transitions:
                target = s.transitions[sym]
                sig[sym] = find_group(target.id, partitions)
            else:
                sig[sym] = -1  # sin transicion
        # Convertir simbolos a str para que sean comparables (frozenset no es < str)
        return tuple(sorted(sig.items(), key=lambda kv: str(kv[0])))

    # Agrupar estados por su firma
    by_sig = {}
    for sid in group_list:
        sig = signature(sid)
        by_sig.setdefault(sig, set()).add(sid)

    return [frozenset(v) for v in by_sig.values()]


def _build_minimal_dfa(original: DFA, partitions, find_group) -> DFA:
    """Construye el DFA minimo a partir de la particion final."""
    state_map = {s.id: s for s in original.states}
    start_group = find_group(original.start.id, partitions)

    min_dfa = DFA(alphabet=original.alphabet)
    group_to_min = {}

    for i, group in enumerate(partitions):
        rep = state_map[next(iter(group))]   # representante del grupo
        ms = DfaState(
            id=i,
            nfa_states=frozenset().union(*(state_map[sid].nfa_states for sid in group)),
            is_accept=rep.is_accept,
            token_name=rep.token_name,
            action=rep.action,
        )
        min_dfa.states.append(ms)
        if ms.is_accept:
            min_dfa.accept_states.append(ms)
        group_to_min[i] = ms

    min_dfa.start = group_to_min[start_group]

    # Copiar transiciones usando representantes
    for i, group in enumerate(partitions):
        rep = state_map[next(iter(group))]
        ms = group_to_min[i]
        for sym, target in rep.transitions.items():
            target_group = find_group(target.id, partitions)
            ms.transitions[sym] = group_to_min[target_group]

    return min_dfa


# ---------------------------------------------------------------------------
# Pipeline completo: NFA -> DFA -> DFA minimo
# ---------------------------------------------------------------------------

def build_lexer_dfa(nfa: NFA) -> DFA:
    """Atajo: NFA -> DFA -> DFA minimo en un solo paso."""
    dfa = nfa_to_dfa(nfa)
    return minimize_dfa(dfa)
