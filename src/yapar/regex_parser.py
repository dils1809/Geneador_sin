"""
M2 - Parser de expresiones regulares a AST

Convierte un string como  [a-z]([a-z]|[0-9])*  en un arbol de nodos.

Gramatica (precedencia de menor a mayor):
  expr   -> concat ('|' concat)*       <- alternancia
  concat -> repeat repeat*             <- concatenacion
  repeat -> atom ('*' | '+' | '?')*   <- repeticion
  atom   -> CHAR | '.' | '[' clase ']' | '(' expr ')'

Los nodos del AST:
  Char(c)           - un caracter literal
  AnyChar()         - punto, cualquier caracter
  CharClass(chars)  - clase de caracteres [abc] o [a-z]
  Concat(l, r)      - concatenacion
  Alt(l, r)         - alternancia l|r
  Star(e)           - Kleene star e*
  Plus(e)           - e+ = ee*
  Option(e)         - e? = e|eps
"""

from dataclasses import dataclass


# --- Nodos del AST ---

@dataclass
class Char:
    c: str

@dataclass
class AnyChar:
    pass

@dataclass
class CharClass:
    chars: frozenset
    negated: bool = False

@dataclass
class Concat:
    left: object
    right: object

@dataclass
class Alt:
    left: object
    right: object

@dataclass
class Star:
    expr: object

@dataclass
class Plus:
    expr: object

@dataclass
class Option:
    expr: object

@dataclass
class Epsilon:
    pass


# --- Parser recursivo descendente ---

class RegexParser:
    def __init__(self, pattern: str):
        self.s = pattern
        self.pos = 0

    def peek(self):
        if self.pos < len(self.s):
            return self.s[self.pos]
        return None

    def consume(self, expected=None):
        ch = self.s[self.pos]
        if expected and ch != expected:
            raise SyntaxError(f"Se esperaba '{expected}', se obtuvo '{ch}' en pos {self.pos}")
        self.pos += 1
        return ch

    def parse(self):
        node = self._expr()
        if self.pos != len(self.s):
            raise SyntaxError(f"Caracter inesperado '{self.peek()}' en pos {self.pos}")
        return node

    def _expr(self):
        node = self._concat()
        while self.peek() == '|':
            self.consume('|')
            right = self._concat()
            node = Alt(node, right)
        return node

    def _concat(self):
        node = self._repeat()
        while self.peek() not in (None, '|', ')'):
            right = self._repeat()
            node = Concat(node, right)
        return node

    def _repeat(self):
        node = self._atom()
        while self.peek() in ('*', '+', '?'):
            op = self.consume()
            if op == '*':
                node = Star(node)
            elif op == '+':
                node = Plus(node)
            else:
                node = Option(node)
        return node

    def _atom(self):
        ch = self.peek()
        if ch is None:
            return Epsilon()
        if ch == '(':
            self.consume('(')
            node = self._expr()
            self.consume(')')
            return node
        if ch == '[':
            return self._char_class()
        if ch == '.':
            self.consume('.')
            return AnyChar()
        if ch == '\\':
            self.consume('\\')
            escaped = self.consume()
            return Char(_unescape(escaped))
        if ch == "'":
            return self._quoted_char()
        if ch == '"':
            return self._double_quoted_string()
        # Guion bajo = cualquier caracter (wildcard en YALex)
        if ch == '_':
            self.consume()
            return AnyChar()
        # Caracter literal simple (excepto metacaracteres)
        if ch not in ('*', '+', '?', '|', ')', ']'):
            self.consume()
            return Char(ch)
        raise SyntaxError(f"Caracter inesperado '{ch}' en pos {self.pos}")

    def _double_quoted_string(self):
        """
        Maneja strings con comillas dobles: "class" "if" ":="
        Se expanden como concatenacion de caracteres individuales.
        """
        self.consume('"')
        chars = []
        while self.peek() is not None and self.peek() != '"':
            if self.peek() == '\\':
                self.consume('\\')
                chars.append(Char(_unescape(self.consume())))
            else:
                chars.append(Char(self.consume()))
        self.consume('"')
        if not chars:
            return Epsilon()
        node = chars[0]
        for c in chars[1:]:
            node = Concat(node, c)
        return node

    def _quoted_char(self):
        """Maneja caracteres con comillas simples como en YALex: '+'"""
        self.consume("'")
        if self.peek() == '\\':
            self.consume('\\')
            c = _unescape(self.consume())
        else:
            c = self.consume()
        self.consume("'")
        return Char(c)

    def _char_class(self):
        """Parsea clases de caracteres: [a-z0-9] o [^abc]"""
        self.consume('[')
        negated = False
        if self.peek() == '^':
            self.consume('^')
            negated = True
        chars = set()
        while self.peek() != ']':
            if self.peek() == '"':
                # string entre comillas dobles dentro de clase: ["0123456789"]
                self.consume('"')
                while self.peek() is not None and self.peek() != '"':
                    if self.peek() == '\\':
                        self.consume('\\')
                        chars.add(_unescape(self.consume()))
                    else:
                        chars.add(self.consume())
                self.consume('"')
                continue
            elif self.peek() == "'":
                # caracter entre comillas simples dentro de clase
                self.consume("'")
                c = self.consume()
                if self.peek() == "'":
                    self.consume("'")
            elif self.peek() == '\\':
                self.consume('\\')
                c = _unescape(self.consume())
            else:
                c = self.consume()
            # rango: a-z
            if self.peek() == '-' and self.s[self.pos+1] != ']':
                self.consume('-')
                if self.peek() == "'":
                    self.consume("'")
                    end = self.consume()
                    if self.peek() == "'":
                        self.consume("'")
                else:
                    end = self.consume()
                for code in range(ord(c), ord(end)+1):
                    chars.add(chr(code))
            else:
                chars.add(c)
        self.consume(']')
        return CharClass(frozenset(chars), negated=negated)


def _unescape(c: str) -> str:
    return {'n': '\n', 't': '\t', 'r': '\r', 's': ' ', '0': '\0',
            '"': '"', "'": "'"}.get(c, c)


def parse_regex(pattern: str):
    """Punto de entrada: string -> nodo AST raiz."""
    return RegexParser(pattern).parse()
