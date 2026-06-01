"""
M8 - Parser de MessiScript (sintaxis REAL del repo Erawaa/MessiScriptInterpreter)

MessiScript es un lenguaje esoterico donde los comandos son frases en espanol.
Este parser maneja el archivo fibonacci.messi y otros programas reales.

Caracteristicas del parser real:
  - Case-insensitive: "La agarra Messi" == "la agarra messi"
  - Comentarios: todo despues de # en cada frase se ignora
  - Multiples comandos por linea separados por punto (.)
  - Marcador final: "le pega messi" o cualquier variante de "gol"
  - "Va Messi, frase": el valor se calcula por conteo de palabras

Comandos (14):
  la agarra messi         INICIO
  va messi [frase]        ASSIGN  (sustantivos +1, adjetivos *2, futbol negacion)
  ankara/ancora messi     ZERO    (poner celda en 0)
  la mueve messi derecha  RIGHT
  la mueve messi izquierda LEFT
  juega messi             PRINT_NUM
  la pisa messi           PRINT_CHAR
  siempre messi           INPUT_NUM
  gambetea messi          INPUT_CHAR
  sigue messi             LOOP_START
  vuelve messi            LOOP_END
  corre messi             COPY
  amaga messi             PASTE
  le pega messi / gol     FIN
"""

import re
from dataclasses import dataclass, field


@dataclass
class MessiToken:
    tipo:   str   # INICIO, ASSIGN, ZERO, RIGHT, LEFT, PRINT_NUM, PRINT_CHAR,
                  # INPUT_NUM, INPUT_CHAR, LOOP_START, LOOP_END, COPY, PASTE, FIN
    valor:  str   # frase original
    linea:  int   # numero de linea en el archivo


# Patrones de comandos (se aplican en orden — el primero que hace match gana)
# Todos se comparan en lowercase sin puntuacion extra
_PATTERNS = [
    (r"la\s+agarra\s+messi",                       "INICIO"),
    (r"le\s+pega\s+messi",                          "FIN"),
    (r"[il][ea]\s+pega\s+messi",                    "FIN"),
    (r"gol",                                         "FIN"),
    (r"la\s+mueve\s+messi\s+por\s+la\s+derecha",   "RIGHT"),
    (r"la\s+mueve\s+messi\s+por\s+la\s+izquierda", "LEFT"),
    (r"la\s+mueve\s+messi\s+derecha",               "RIGHT"),
    (r"la\s+mueve\s+messi\s+izquierda",             "LEFT"),
    (r"gambetea\s+messi",                            "INPUT_CHAR"),
    (r"siempre\s+messi",                             "INPUT_NUM"),
    (r"la\s+pisa\s+messi",                           "PRINT_CHAR"),
    (r"juega\s+messi",                               "PRINT_NUM"),
    (r"an[ck]ara\s+messi",                           "ZERO"),
    (r"an[ck]ora\s+messi",                           "ZERO"),
    (r"corre\s+messi",                               "COPY"),
    (r"amaga\s+messi",                               "PASTE"),
    (r"sigue\s+messi",                               "LOOP_START"),
    (r"vuelve\s+messi",                              "LOOP_END"),
    (r"va\s+messi",                                  "ASSIGN"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), t) for p, t in _PATTERNS]


def _strip_comment(s: str) -> str:
    """Elimina comentarios (#...) de una frase."""
    idx = s.find("#")
    return s[:idx].strip() if idx >= 0 else s.strip()


def _classify(frase: str) -> str | None:
    """Determina el tipo de comando de una frase. None si no reconoce."""
    f = frase.strip().lower()
    if not f:
        return None
    for pat, tipo in _COMPILED:
        if pat.search(f):
            return tipo
    return None


def tokenize_messi(text: str) -> list[MessiToken]:
    """
    Tokeniza texto MessiScript real.
    Maneja comentarios, mayusculas mixtas, multiples comandos por linea.
    Devuelve lista de MessiToken.
    """
    tokens = []

    for lineno, raw_line in enumerate(text.splitlines(), 1):
        # Quitar comentario de la linea completa si la # esta al inicio
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Dividir por punto para obtener frases/comandos individuales
        frases = line.split(".")
        for raw_frase in frases:
            frase = _strip_comment(raw_frase)
            if not frase:
                continue

            tipo = _classify(frase)
            if tipo is not None:
                tokens.append(MessiToken(tipo=tipo, valor=frase.strip(), linea=lineno))
            # Si no reconoce la frase la ignora (puede ser texto descriptivo)

    return tokens


def validate_messi(tokens: list[MessiToken]) -> tuple[bool, str]:
    """
    Valida la estructura del programa MessiScript:
    - Debe comenzar con INICIO
    - Debe terminar con FIN
    - Loops LOOP_START/LOOP_END deben estar balanceados

    Devuelve (valido, mensaje_error).
    """
    if not tokens:
        return False, "Programa vacio — se esperaba 'la agarra messi'"

    if tokens[0].tipo != "INICIO":
        return False, (f"Linea {tokens[0].linea}: el programa debe comenzar "
                       f"con 'la agarra messi', se encontro '{tokens[0].tipo}'")

    if tokens[-1].tipo != "FIN":
        return False, (f"El programa debe terminar con 'le pega messi' o 'gol', "
                       f"ultimo token: '{tokens[-1].tipo}' en linea {tokens[-1].linea}")

    # Verificar balance de loops
    depth = 0
    for tok in tokens:
        if tok.tipo == "LOOP_START":
            depth += 1
        elif tok.tipo == "LOOP_END":
            depth -= 1
            if depth < 0:
                return False, (f"Linea {tok.linea}: 'vuelve messi' sin "
                               f"'sigue messi' correspondiente")
    if depth != 0:
        return False, f"{depth} 'sigue messi' sin cerrar con 'vuelve messi'"

    return True, ""


def parse_messi(text: str) -> dict:
    """
    Valida un programa MessiScript (sintaxis real).
    Devuelve: valid, tokens, error, token_count, estadisticas
    """
    try:
        tokens = tokenize_messi(text)
        valid, error = validate_messi(tokens)

        # Estadisticas por tipo de comando
        stats = {}
        for tok in tokens:
            stats[tok.tipo] = stats.get(tok.tipo, 0) + 1

        return {
            "valid":       valid,
            "tokens":      [(t.tipo, t.valor, t.linea) for t in tokens],
            "error":       error if not valid else None,
            "token_count": len(tokens),
            "estadisticas": stats,
            "lineas":      max((t.linea for t in tokens), default=0),
        }
    except Exception as ex:
        return {
            "valid":       False,
            "tokens":      [],
            "error":       f"Error inesperado: {ex}",
            "token_count": 0,
            "estadisticas": {},
            "lineas":      0,
        }


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    else:
        text = ("La agarra Messi. Va Messi, dando clases. "
                "Juega Messi. !gol!")

    r = parse_messi(text)
    print(f"Valido:  {r['valid']}")
    print(f"Tokens:  {r['token_count']}")
    print(f"Lineas:  {r['lineas']}")
    if r["error"]:
        print(f"Error:   {r['error']}")
    print("\nEstadisticas:")
    for tipo, n in sorted(r["estadisticas"].items()):
        print(f"  {tipo:15} {n}")
    print("\nPrimeros 10 tokens:")
    for tok in r["tokens"][:10]:
        tipo, val, ln = tok
        print(f"  L{ln:3} {tipo:15} {val[:50]}")
