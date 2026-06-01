"""M6 - Tablas SLR(1), LALR y LL(1)"""
from .lr0 import LR0Automaton, Item
from .first_follow import compute_first, compute_follow, _first_seq

SHIFT  = "shift"
REDUCE = "reduce"
ACCEPT = "accept"
GOTO   = "goto"


def build_slr1_table(productions, terminals, start):
    """Construye tabla ACTION y GOTO para SLR(1)."""
    first  = compute_first(productions, set(terminals))
    follow = compute_follow(productions, start, first)
    lr0    = LR0Automaton(productions, start)
    non_terminals = {p.head for p in productions}

    action = {}   # (state_id, terminal) -> (tipo, valor)
    goto   = {}   # (state_id, non_terminal) -> state_id
    # SLR(1) solo reporta conflictos REALES en la tabla (no todos los LR(0))
    # Los conflictos LR(0) se resuelven con FOLLOW sets en SLR(1)
    conflicts = []

    prod_list = productions  # indice = posicion en la lista

    for state in lr0.states:
        sid = state.id
        for item in state.items:
            sym = item.at_dot()
            if sym is not None:
                # SHIFT o GOTO
                if sym in state.transitions:
                    ns = state.transitions[sym]
                    if sym not in non_terminals:
                        key = (sid, sym)
                        if key in action and action[key] != (SHIFT, ns.id):
                            conflicts.append({"state": sid, "type": "conflict en action", "symbol": sym})
                        action[key] = (SHIFT, ns.id)
                    else:
                        goto[(sid, sym)] = ns.id
            else:
                # REDUCE o ACCEPT
                prod_head = item.head
                if prod_head == start + "'":
                    action[(sid, "$")] = (ACCEPT, 0)
                else:
                    # Encontrar indice de la produccion
                    for i, p in enumerate(prod_list):
                        if p.head == prod_head and tuple(p.body) == item.body:
                            for t in follow.get(prod_head, set()):
                                key = (sid, t)
                                if key in action and action[key] != (REDUCE, i):
                                    conflicts.append({"state": sid, "type": "shift/reduce SLR", "symbol": t})
                                action[key] = (REDUCE, i)
                            break

    return {"action": action, "goto": goto, "conflicts": conflicts, "lr0": lr0}


def build_ll1_table(productions, terminals, start):
    """Construye tabla predictiva LL(1): M[A, a] = produccion."""
    first  = compute_first(productions, set(terminals))
    follow = compute_follow(productions, start, first)
    table  = {}   # (non_terminal, terminal) -> Production
    conflicts = []

    for prod in productions:
        first_body = _first_seq(prod.body if prod.body else [], first)
        for t in first_body:
            if t == "epsilon":
                for f in follow.get(prod.head, set()):
                    key = (prod.head, f)
                    if key in table:
                        conflicts.append({"non_terminal": prod.head, "terminal": f, "type": "LL1 conflict"})
                    table[key] = prod
            else:
                key = (prod.head, t)
                if key in table:
                    conflicts.append({"non_terminal": prod.head, "terminal": t, "type": "LL1 conflict"})
                table[key] = prod

    return {"table": table, "conflicts": conflicts, "first": first, "follow": follow}


def parse_slr1(tokens, action, goto, productions, start):
    """
    Simula el parser SLR(1) sobre una lista de tokens.
    tokens: lista de (tipo, lexema)
    Devuelve lista de pasos (estado, simbolo, accion).
    """
    stack  = [0]
    input_ = list(tokens) + [("$", "$")]
    steps  = []
    pos    = 0

    while True:
        state = stack[-1]
        tok_type, tok_val = input_[pos]
        key = (state, tok_type)
        if key not in action:
            raise SyntaxError(
                f"Error sintactico en '{tok_val}' (estado {state}, token '{tok_type}')"
            )
        act, val = action[key]
        steps.append((state, tok_type, act, val))

        if act == ACCEPT:
            break
        elif act == SHIFT:
            stack.append(tok_type)
            stack.append(val)
            pos += 1
        elif act == REDUCE:
            prod = productions[val]
            for _ in range(len(prod.body) * 2):
                stack.pop()
            state = stack[-1]
            nt = prod.head
            stack.append(nt)
            stack.append(goto[(state, nt)])

    return steps
def parse_slr1_tree(tokens, action, goto, productions):
    """
    Simula el parser SLR(1) y construye el arbol de derivacion.
    tokens: lista de (tipo, lexema)
    Devuelve (steps, ParseNode raiz)
    """
    from .parse_tree import ParseNode
    stack     = [0]
    sym_stack = []
    input_    = list(tokens) + [("$", "$")]
    steps     = []
    pos       = 0

    while True:
        state    = stack[-1]
        tok_type, tok_val = input_[pos]
        key = (state, tok_type)

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
            root = sym_stack[-1] if sym_stack else ParseNode("ACCEPT", [])
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
