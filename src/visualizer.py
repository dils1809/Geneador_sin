"""
Modulo de visualizacion de automatas con Graphviz.

Genera diagramas PNG para:
  - NFA  (Thompson)
  - DFA  (subconjuntos)
  - DFA minimo (Hopcroft)
  - Automata LR(0)
"""

import os
import tempfile
import graphviz


# ── NFA ──────────────────────────────────────────────────────────────────────

def nfa_to_dot(nfa, title="NFA (Thompson)") -> graphviz.Digraph:
    dot = graphviz.Digraph(comment=title)
    dot.attr(rankdir="LR", label=title, fontsize="14", labelloc="t")
    dot.attr("node", shape="circle", fontname="Consolas")

    # Nodo invisible de inicio
    dot.node("__start__", "", shape="none", width="0")
    dot.edge("__start__", f"q{nfa.start.id}")

    for state in nfa.states:
        sid = f"q{state.id}"
        shape = "doublecircle" if state.is_accept else "circle"
        label = sid
        if state.is_accept and hasattr(state, "token_name") and state.token_name:
            label = f"{sid}\n{state.token_name}"
        dot.node(sid, label, shape=shape)

    for state in nfa.states:
        for sym, target in state.transitions:
            if sym is None:
                label = "ε"
            elif sym == "ANY":
                label = "."
            elif isinstance(sym, frozenset):
                chars = sorted(sym)
                if len(chars) > 6:
                    label = f"[{chars[0]}-{chars[-1]}]"
                else:
                    label = "[" + "".join(chars) + "]"
            else:
                label = str(sym)
            dot.edge(f"q{state.id}", f"q{target.id}", label=label)

    return dot


# ── DFA ──────────────────────────────────────────────────────────────────────

def dfa_to_dot(dfa, title="DFA") -> graphviz.Digraph:
    dot = graphviz.Digraph(comment=title)
    dot.attr(rankdir="LR", label=title, fontsize="14", labelloc="t")
    dot.attr("node", shape="circle", fontname="Consolas")

    dot.node("__start__", "", shape="none", width="0")
    dot.edge("__start__", f"D{dfa.start.id}")

    for state in dfa.states:
        sid = f"D{state.id}"
        shape = "doublecircle" if state.is_accept else "circle"
        label = sid
        if state.is_accept and state.token_name:
            label = f"{sid}\n{state.token_name}"
        dot.node(sid, label, shape=shape)

    for state in dfa.states:
        # Agrupar transiciones con el mismo destino
        grouped = {}
        for sym, target in state.transitions.items():
            key = f"D{target.id}"
            if isinstance(sym, frozenset):
                chars = sorted(sym)
                lbl = f"[{chars[0]}-{chars[-1]}]" if len(chars) > 4 else "[" + "".join(chars) + "]"
            elif sym == "ANY":
                lbl = "."
            else:
                lbl = str(sym)
            grouped.setdefault(key, []).append(lbl)

        for target_sid, labels in grouped.items():
            edge_label = ", ".join(sorted(labels))
            dot.edge(f"D{state.id}", target_sid, label=edge_label)

    return dot


# ── LR(0) ────────────────────────────────────────────────────────────────────

def lr0_to_dot(lr0, title="Automata LR(0)") -> graphviz.Digraph:
    dot = graphviz.Digraph(comment=title)
    dot.attr(rankdir="LR", label=title, fontsize="14", labelloc="t")
    dot.attr("node", shape="box", fontname="Consolas", fontsize="10")

    dot.node("__start__", "", shape="none", width="0")
    dot.edge("__start__", "I0")

    for state in lr0.states:
        sid = f"I{state.id}"
        items_text = "\n".join(str(item) for item in sorted(state.items, key=str))
        dot.node(sid, f"I{state.id}\n{items_text}")

    for state in lr0.states:
        for sym, target in state.transitions.items():
            dot.edge(f"I{state.id}", f"I{target.id}", label=str(sym))

    return dot


# ── Render a PNG bytes ────────────────────────────────────────────────────────

def render_to_png(graph: graphviz.Digraph) -> bytes:
    """Renderiza el grafo y devuelve los bytes PNG."""
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "graph")
        graph.render(path, format="png", cleanup=True)
        with open(path + ".png", "rb") as f:
            return f.read()


def parse_tree_to_dot(root, title="Arbol de Derivacion"):
    """Convierte un ParseNode en un grafo Graphviz."""
    import graphviz
    dot = graphviz.Digraph(comment=title)
    dot.attr(rankdir="TB", label=title, fontsize="14", labelloc="t")
    dot.attr("node", fontname="Consolas", fontsize="11")
    counter = [0]

    def add_node(node):
        nid = str(counter[0])
        counter[0] += 1
        if node.is_terminal():
            label = f"{node.head}\n{node.value!r}"
            dot.node(nid, label, shape="box",
                     style="filled", fillcolor="#a6e3a1", color="#1e1e2e")
        else:
            dot.node(nid, node.head, shape="ellipse",
                     style="filled", fillcolor="#89b4fa", color="#1e1e2e",
                     fontcolor="#1e1e2e")
        for child in node.children:
            cid = add_node(child)
            dot.edge(nid, cid)
        return nid

    add_node(root)
    return dot
