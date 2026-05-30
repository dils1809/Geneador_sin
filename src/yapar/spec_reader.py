"""
M1 - Lector de especificaciones YAPar (.yapar)

Un archivo .yapar tiene dos secciones:
  %token ID NUM PLUS ...
  %%
  expr : expr PLUS term
       | term
       ;

Este modulo lee ese texto y produce una estructura lista para M4 (FIRST/FOLLOW).
"""

import re
from dataclasses import dataclass


@dataclass
class Production:
    head: str
    body: list


@dataclass
class YaparSpec:
    tokens: list
    productions: list
    start_symbol: str


def load_yapar(path: str) -> YaparSpec:
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    text = re.sub(r'\(\*.*?\*\)', '', text, flags=re.DOTALL)
    tokens = _extract_tokens(text)
    productions, start = _extract_productions(text)
    return YaparSpec(tokens=tokens, productions=productions, start_symbol=start)


def _extract_tokens(text: str) -> list:
    tokens = []
    for m in re.finditer(r'%token\s+(.+)', text):
        tokens.extend(m.group(1).split())
    return tokens


def _extract_productions(text: str):
    parts = text.split('%%', 1)
    grammar_text = parts[1] if len(parts) > 1 else text
    productions = []
    start_symbol = ""
    for rule_match in re.finditer(r'(\w+)\s*:(.*?);', grammar_text, re.DOTALL):
        head = rule_match.group(1)
        if not start_symbol:
            start_symbol = head
        for alt in rule_match.group(2).split('|'):
            symbols = alt.split()
            productions.append(Production(head=head, body=symbols if symbols else []))
    return productions, start_symbol
