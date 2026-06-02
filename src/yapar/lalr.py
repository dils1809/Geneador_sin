"""
LALR — Look-Ahead LR parser

Diferencia con SLR(1):
  SLR(1) usa FOLLOW(A) — conjunto global — para decidir cuando reducir.
  LALR usa lookaheads ESPECIFICOS por estado: cada item de reduccion en
  cada estado tiene su propio conjunto de lookaheads, calculados por
  propagacion a traves del automata LR(0).

  Resultado: LALR tiene el mismo numero de estados que LR(0) y SLR(1),
  pero menos conflictos que SLR(1) en gramaticas ambiguas moderadas.

Algoritmo Dragon Book 4.62 (propagacion de lookaheads):
  1. Construir LR(0).
  2. Para cada item kernel de cada estado I:
       - Agregar simbolo especial DUMMY al item y calcular su CLOSURE.
       - Si FIRST(beta DUMMY) contiene terminales reales -> espontaneos.
       - Si DUMMY llega al final -> propagar desde el item origen.
  3. Inicializar: I0's start item tiene {$}.
  4. Propagar hasta punto fijo.
  5. Construir ACTION/GOTO igual que SLR(1) pero usando los lookaheads
     calculados en vez del FOLLOW global.
"""

from .lr0 import LR0Automaton, Item
from .first_follow import compute_first, compute_follow, _first_seq

SHIFT  = "shift"
REDUCE = "reduce"
ACCEPT = "accept"
DUMMY  = "##DUMMY##"   # simbolo especial para deteccion de lookaheads


def build_lalr_table(productions, terminals, start):
    """
    Construye tablas ACTION y GOTO por el algoritmo LALR.
    Devuelve: action, goto, conflicts, lookaheads, lr0, first, follow.
    """
    first  = compute_first(productions, set(terminals))
    follow = compute_follow(productions, start, first)
    lr0    = LR0Automaton(productions, start)
    non_terminals = {p.head for p in productions}

    # Agregar DUMMY al dict first para que _first_seq lo reconozca
    first[DUMMY] = {DUMMY}

    # Calcular lookaheads por propagacion
    lookaheads = _compute_lookaheads(lr0, productions, first, start, follow)

    action    = {}
    goto      = {}
    conflicts = []

    for state in lr0.states:
        sid = state.id
        for item in state.items:
            sym = item.at_dot()
            if sym is not None:
                if sym in state.transitions:
                    ns = state.transitions[sym]
                    if sym not in non_terminals:
                        key = (sid, sym)
                        if key in action and action[key] != (SHIFT, ns.id):
                            conflicts.append({
                                "state": sid, "type": "shift/reduce LALR",
                                "symbol": sym
                            })
                        action[key] = (SHIFT, ns.id)
                    else:
                        goto[(sid, sym)] = ns.id
            else:
                # Item de reduccion
                if item.head == start + "'":
                    action[(sid, "$")] = (ACCEPT, 0)
                    continue
                la_set = lookaheads.get((sid, item), set())
                for i, p in enumerate(productions):
                    if p.head == item.head and tuple(p.body) == item.body:
                        for la in la_set:
                            key = (sid, la)
                            if key in action and action[key] != (REDUCE, i):
                                conflicts.append({
                                    "state": sid,
                                    "type": "shift/reduce LALR"
                                             if action[key][0] == SHIFT
                                             else "reduce/reduce LALR",
                                    "symbol": la,
                                })
                            else:
                                action[key] = (REDUCE, i)
                        break

    return {
        "action":     action,
        "goto":       goto,
        "conflicts":  conflicts,
        "lookaheads": lookaheads,
        "lr0":        lr0,
        "first":      first,
        "follow":     follow,
    }


def _compute_lookaheads(lr0, productions, first, start, follow):
    """
    Calcula lookaheads LALR por propagacion (Dragon Book alg 4.62).
    Usa follow como fallback para garantizar correctitud.
    """
    # Inicializar lookaheads vacios para cada (state_id, item)
    la = {}
    for state in lr0.states:
        for item in state.items:
            la[(state.id, item)] = set()

    # Item aumentado en I0 tiene {$} espontaneo
    aug_item = Item(start + "'", (start,), 0)
    if (0, aug_item) in la:
        la[(0, aug_item)].add("$")

    # Mapa de propagacion: (sid, item) -> lista de (sid_destino, item_destino)
    propagate = {k: [] for k in la}

    for state in lr0.states:
        for kitem in _kernel(state):
            # Calcular closure de kitem con lookahead DUMMY
            closure_w_dummy = _closure_with_lookahead(kitem, DUMMY, lr0, first)
            for (ci, la_sym) in closure_w_dummy:
                sym = ci.at_dot()
                if sym is None or sym not in state.transitions:
                    continue
                next_state = state.transitions[sym]
                adv = ci.advance()
                if adv not in next_state.items:
                    continue
                key_dest = (next_state.id, adv)
                if la_sym == DUMMY:
                    # Propagacion
                    propagate.setdefault((state.id, kitem), []).append(key_dest)
                else:
                    # Lookahead espontaneo
                    la.setdefault(key_dest, set()).add(la_sym)

    # Punto fijo de propagacion
    changed = True
    while changed:
        changed = False
        for src, dests in propagate.items():
            for dest in dests:
                before = len(la.get(dest, set()))
                la.setdefault(dest, set()).update(la.get(src, set()))
                if len(la.get(dest, set())) != before:
                    changed = True

    # Fallback: para items de reduccion sin lookaheads, usar FOLLOW global
    non_terminals = {p.head for p in productions}
    for state in lr0.states:
        for item in state.items:
            if item.at_dot() is None and item.head != start + "'":
                key = (state.id, item)
                if not la.get(key):
                    la[key] = follow.get(item.head, set()).copy()

    return la


def _kernel(state):
    """Items del nucleo de un estado (dot > 0 o item aumentado en I0)."""
    result = []
    for item in state.items:
        if item.dot > 0 or item.head.endswith("'"):
            result.append(item)
    return result


def _closure_with_lookahead(item, lookahead, lr0, first):
    """
    Calcula el closure de {[item, lookahead]} propagando lookaheads.
    Devuelve set de (item, lookahead).
    """
    result = {(item, lookahead)}
    worklist = [(item, lookahead)]
    while worklist:
        it, la = worklist.pop()
        sym = it.at_dot()
        if sym is None:
            continue
        # Para cada produccion que empieza con sym
        from .lr0 import Item as LR0Item
        # Buscar en las producciones del lr0
        for prod in lr0.productions:
            if prod.head != sym:
                continue
            new_item = LR0Item(prod.head, tuple(prod.body), 0)
            # FIRST(beta la) donde beta = resto del cuerpo despues del punto
            beta = list(it.body[it.dot + 1:]) + ([la] if la != "epsilon" else [])
            beta_first = _first_seq(beta, first) if beta else {la}
            if not beta_first:
                beta_first = {la}
            for t in beta_first:
                if t == "epsilon":
                    t = la
                pair = (new_item, t)
                if pair not in result:
                    result.add(pair)
                    worklist.append(pair)
    return result


def parse_lalr(tokens, action, goto, productions):
    """Simula el parser LALR. Devuelve (pasos, arbol_raiz)."""
    from .parse_tree import ParseNode
    stack     = [0]
    sym_stack = []
    input_    = list(tokens) + [("$", "$")]
    steps     = []
    pos       = 0

    while True:
        state    = stack[-1]
        tok_type = input_[pos][0]
        tok_val  = input_[pos][1]
        key      = (state, tok_type)

        if key not in action:
            raise SyntaxError(
                f"Error sintactico en '{tok_val}' "
                f"(estado {state}, token '{tok_type}')"
            )

        act, val = action[key]
        steps.append({
            "stack":  list(stack),
            "input":  [t[0] for t in input_[pos:]],
            "action": f"{act} {val}",
        })

        if act == ACCEPT:
            root = sym_stack[-1] if sym_stack else ParseNode("OK", [])
            return steps, root
        elif act == SHIFT:
            sym_stack.append(ParseNode(tok_type, [], value=tok_val))
            stack.append(tok_type)
            stack.append(val)
            pos += 1
        elif act == REDUCE:
            prod = productions[val]
            children = []
            for _ in range(len(prod.body)):
                stack.pop()
                stack.pop()
                children.insert(0, sym_stack.pop())
            node = ParseNode(prod.head, children)
            sym_stack.append(node)
            state = stack[-1]
            stack.append(prod.head)
            stack.append(goto[(state, prod.head)])
