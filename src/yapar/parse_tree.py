"""
Arbol de derivacion (parse tree) para parsers SLR(1) y LALR.

Un ParseNode representa un nodo del arbol:
  - head:     simbolo de la gramatica (terminal o no-terminal)
  - children: hijos del nodo (vacios para terminales)
  - value:    lexema real (solo para terminales)
"""

from dataclasses import dataclass, field


@dataclass
class ParseNode:
    head:     str
    children: list = field(default_factory=list)
    value:    str  = ""

    def is_terminal(self):
        return len(self.children) == 0

    def __repr__(self):
        if self.is_terminal():
            return f"[{self.head}:{self.value!r}]"
        kids = ", ".join(repr(c) for c in self.children)
        return f"({self.head} -> {kids})"

    def pretty(self, indent=0):
        pad = "  " * indent
        if self.is_terminal():
            return f"{pad}{self.head}: {self.value!r}"
        lines = [f"{pad}{self.head}"]
        for c in self.children:
            lines.append(c.pretty(indent + 1))
        return "\n".join(lines)