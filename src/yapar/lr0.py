from dataclasses import dataclass, field

@dataclass(frozen=True)
class Item:
    head: str
    body: tuple
    dot: int
    def advance(self): return Item(self.head, self.body, self.dot+1)
    def at_dot(self): return self.body[self.dot] if self.dot < len(self.body) else None
    def __repr__(self): 
        b = list(self.body); b.insert(self.dot, ".")
        return f"[{self.head} -> {' '.join(b)}]"

@dataclass
class LR0State:
    id: int
    items: frozenset
    transitions: dict = field(default_factory=dict)
    def __hash__(self): return hash(self.id)

class LR0Automaton:
    def __init__(self, productions, start):
        self.productions = productions
        self.start = start
        self.states = []
        self.conflicts = []
        self._build()

    def _closure(self, items):
        closure = set(items)
        changed = True
        while changed:
            changed = False
            for item in list(closure):
                sym = item.at_dot()
                if sym is None: continue
                for prod in self.productions:
                    if prod.head == sym:
                        ni = Item(prod.head, tuple(prod.body), 0)
                        if ni not in closure:
                            closure.add(ni); changed = True
        return frozenset(closure)

    def _goto(self, items, symbol):
        moved = {i.advance() for i in items if i.at_dot() == symbol}
        return self._closure(moved) if moved else frozenset()

    def _build(self):
        # Estado inicial: item aumentado S' -> . S
        start_item = Item(self.start + "'", (self.start,), 0)
        init = self._closure({start_item})
        s0 = LR0State(0, init)
        self.states.append(s0)
        mapping = {init: s0}
        worklist = [s0]
        while worklist:
            state = worklist.pop()
            symbols = {i.at_dot() for i in state.items if i.at_dot() is not None}
            for sym in symbols:
                goto = self._goto(state.items, sym)
                if not goto: continue
                if goto not in mapping:
                    ns = LR0State(len(self.states), goto)
                    self.states.append(ns); mapping[goto] = ns; worklist.append(ns)
                state.transitions[sym] = mapping[goto]
        self._detect_conflicts()

    def _detect_conflicts(self):
        for state in self.states:
            shifts = {i.at_dot() for i in state.items if i.at_dot() is not None}
            reduces = {i for i in state.items if i.at_dot() is None}
            for r in reduces:
                for s in shifts:
                    self.conflicts.append({
                        "state": state.id, "type": "shift/reduce",
                        "shift_on": s, "reduce": str(r)
                    })
