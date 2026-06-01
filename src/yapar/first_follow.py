EPSILON = "epsilon"
EOF = "$"

def compute_first(productions, terminals):
    first = {}
    non_terminals = {p.head for p in productions}
    for sym in non_terminals | terminals:
        first[sym] = set()
    for t in terminals:
        first[t] = {t}
    first["epsilon"] = {"epsilon"}
    changed = True
    while changed:
        changed = False
        for prod in productions:
            before = len(first[prod.head])
            first[prod.head] |= _first_seq(prod.body, first)
            if len(first[prod.head]) != before:
                changed = True
    return first

def _first_seq(symbols, first):
    if not symbols:
        return {"epsilon"}
    result = set()
    for sym in symbols:
        sf = first.get(sym, {sym})
        result |= (sf - {"epsilon"})
        if "epsilon" not in sf:
            break
    else:
        result.add("epsilon")
    return result

def compute_follow(productions, start, first):
    non_terminals = {p.head for p in productions}
    follow = {nt: set() for nt in non_terminals}
    follow[start].add("$")
    changed = True
    while changed:
        changed = False
        for prod in productions:
            for i, sym in enumerate(prod.body):
                if sym not in non_terminals:
                    continue
                before = len(follow[sym])
                rest_first = _first_seq(prod.body[i+1:], first)
                follow[sym] |= (rest_first - {"epsilon"})
                if "epsilon" in rest_first:
                    follow[sym] |= follow[prod.head]
                if len(follow[sym]) != before:
                    changed = True
    return follow
