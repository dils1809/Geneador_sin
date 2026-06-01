"""
M8 - Parser del idioma Mam (Maya de Guatemala)

Idioma: Mam
Familia: Maya (rama Mameana)
Hablantes: ~500,000 (tercer idioma maya mas hablado en Guatemala)
Region: Huehuetenango y San Marcos
Fuente academica: ALMG (Academia de Lenguas Mayas de Guatemala), 2009

Estructura gramatical Mam:
  - Orden basico: Sujeto-Verbo-Objeto (SVO) en oraciones simples
  - La negacion 'mi' precede al sujeto
  - Los determinantes 'tuj'/'ti'' preceden al sustantivo
  - Verbos con morfologia aspectual (no implementada completamente aqui)

El parser:
  1. Tokeniza texto Mam usando tabla de vocabulario
  2. Valida estructura gramatical con parser recursivo
  3. Traduce al espanol con diccionario

Para usar con el pipeline YALex/YAPar completo:
  from src.yalex.spec_reader import load_yal
  from src.yapar.spec_reader import load_yapar
  spec = load_yal('examples/mam/mam.yal')
  gram = load_yapar('examples/mam/mam.yapar')
"""

# ── Vocabulario Mam completo ────────────────────────────────────────────────
VOCAB = {
    # Pronombres personales
    "in":            ("PRON_1S", "yo"),
    "at":            ("PRON_2S", "tu"),
    "e":             ("PRON_3S", "el/ella"),
    "oj":            ("PRON_1P", "nosotros"),
    "ey":            ("PRON_3P", "ellos/ellas"),
    # Verbos
    "tzaj":          ("VERBO",   "viene/vienen"),
    "jaw":           ("VERBO",   "come/comen"),
    "b'et":          ("VERBO",   "va/van"),
    "tz'ok":         ("VERBO",   "habla/hablan"),
    "tz'ib'":        ("VERBO",   "escribe/escriben"),
    "xnaq'tzb'il":   ("VERBO",   "ensena/ensenan"),
    "q'on":          ("VERBO",   "duerme/duermen"),
    "b'ixan":        ("VERBO",   "canta/cantan"),
    "tz'aq":         ("VERBO",   "cae/caen"),
    "b'ant":         ("VERBO",   "hace/hacen"),
    # Sustantivos
    "txutx":         ("SUST",    "madre"),
    "tat":           ("SUST",    "padre"),
    "ali":           ("SUST",    "nina"),
    "achin":         ("SUST",    "hombre"),
    "ixim":          ("SUST",    "maiz"),
    "ja":            ("SUST",    "casa"),
    "tnam":          ("SUST",    "pueblo"),
    "b'ix":          ("SUST",    "cancion"),
    "q'an":          ("SUST",    "amarillo/oro"),
    "witz":          ("SUST",    "cerro/montana"),
    "aab'":          ("SUST",    "lluvia"),
    "tx'otx'":       ("SUST",    "tierra"),
    "q'aq'":         ("SUST",    "fuego"),
    "ya'":           ("SUST",    "agua"),
    # Determinantes
    "tuj":           ("DET",     "el/la"),
    "ti'":           ("DET",     "el/la"),
    # Negacion
    "mi":            ("NEG",     "no"),
    # Conjunciones
    "ex":            ("CONJ",    "y"),
    "jte'":          ("CONJ",    "pero"),
    # Adverbios
    "ax":            ("ADV",     "aqui"),
    "qa":            ("ADV",     "alli"),
    # Puntuacion
    ".":             ("PUNTO",   "."),
    ",":             ("COMA",    ","),
}

PRONOMBRES = {"PRON_1S","PRON_2S","PRON_3S","PRON_1P","PRON_3P"}


def tokenize_mam(text):
    """
    Tokeniza texto en idioma Mam.
    Maneja palabras con apostrofe glotalizadas (b'et, tz'ok, etc.)
    Devuelve lista de (tipo, lexema).
    """
    tokens = []
    # Reemplazar signos de puntuacion para separarlos como palabras
    text = text.replace(".", " . ").replace(",", " , ")
    palabras = text.split()
    for p in palabras:
        pl = p.lower()
        if pl in VOCAB:
            tipo, _ = VOCAB[pl]
            tokens.append((tipo, pl))
        else:
            raise ValueError(
                f"Palabra Mam desconocida: '{p}'. "
                f"El Mam usa consonantes glotalizadas (b', tz', q', etc.) — "
                f"verifica la escritura segun la ALMG."
            )
    return tokens


def _parse_fn(tokens, p):
    """Parsea una frase nominal: DET SUST | SUST | ADV SUST | PRON"""
    if p >= len(tokens):
        return None, p
    tipo, lex = tokens[p]
    if tipo in PRONOMBRES:
        return ("PRON", lex), p+1
    if tipo == "DET" and p+1 < len(tokens) and tokens[p+1][0] == "SUST":
        return ("FN", [tokens[p], tokens[p+1]]), p+2
    if tipo == "ADV" and p+1 < len(tokens) and tokens[p+1][0] == "SUST":
        return ("FN", [tokens[p], tokens[p+1]]), p+2
    if tipo == "SUST":
        return ("FN", [tokens[p]]), p+1
    return None, p


def _validate_oracion(tokens, p):
    """
    Valida una oracion Mam.
    Gramatica:
      oracion -> [NEG] frase_nominal VERBO [frase_nominal] PUNTO
               | frase_nominal CONJ frase_nominal VERBO PUNTO
    """
    inicio = p
    negacion = False
    if p < len(tokens) and tokens[p][0] == "NEG":
        negacion = True
        p += 1

    fn1, p = _parse_fn(tokens, p)
    if fn1 is None:
        raise SyntaxError(
            f"Se esperaba sujeto (pronombre o sustantivo) en posicion {p}. "
            f"Recuerda que el orden en Mam es: [mi] Sujeto Verbo [Objeto]."
        )

    # Conjuncion opcional: FN CONJ FN VERBO
    if p < len(tokens) and tokens[p][0] == "CONJ":
        p += 1  # saltar CONJ
        fn2, p = _parse_fn(tokens, p)
        if fn2 is None:
            raise SyntaxError(f"Se esperaba segunda frase nominal despues de la conjuncion en pos {p}")

    if p >= len(tokens) or tokens[p][0] != "VERBO":
        raise SyntaxError(
            f"Se esperaba un VERBO en posicion {p}. "
            f"Verbos Mam: tzaj, jaw, b'et, tz'ok, tz'ib', xnaq'tzb'il, q'on, b'ixan..."
        )
    p += 1

    # Objeto opcional
    fn_obj, p2 = _parse_fn(tokens, p)
    if fn_obj is not None:
        p = p2

    if p >= len(tokens) or tokens[p][0] != "PUNTO":
        raise SyntaxError(
            f"Se esperaba punto (.) al final de la oracion en posicion {p}."
        )
    p += 1
    return p


def validar_mam(tokens):
    """Valida todas las oraciones del texto Mam."""
    p = 0
    oraciones = 0
    while p < len(tokens):
        if tokens[p][0] == "PUNTO":
            p += 1
            continue
        p = _validate_oracion(tokens, p)
        oraciones += 1
    if oraciones == 0:
        raise SyntaxError("No se encontraron oraciones validas en el texto.")
    return oraciones


def traducir_mam(tokens):
    """Traduce tokens Mam al espanol."""
    partes = []
    i = 0
    oracion_actual = []
    while i < len(tokens):
        tipo, lex = tokens[i]
        trad = VOCAB[lex][1]
        if tipo == "PUNTO":
            if oracion_actual:
                # Capitalizar primera palabra de cada oracion
                oracion_actual[0] = oracion_actual[0].capitalize()
                partes.append(" ".join(oracion_actual) + ".")
                oracion_actual = []
        elif tipo == "DET" and i+1 < len(tokens) and tokens[i+1][0] == "SUST":
            sust_trad = VOCAB[tokens[i+1][1]][1]
            oracion_actual.append(f"{trad} {sust_trad}")
            i += 1
        elif tipo == "ADV" and i+1 < len(tokens) and tokens[i+1][0] == "SUST":
            sust_trad = VOCAB[tokens[i+1][1]][1]
            oracion_actual.append(f"{trad} {sust_trad}")
            i += 1
        elif tipo != "COMA":
            oracion_actual.append(trad)
        i += 1
    return " ".join(partes)


def parse_mam(text):
    """
    Valida y traduce texto en idioma Mam.
    Acepta multiples oraciones separadas por punto.

    Returns:
        dict con: valid, tokens, traduccion, oraciones, error
    """
    try:
        tokens = tokenize_mam(text)
        n_oraciones = validar_mam(tokens)
        traduccion  = traducir_mam(tokens)
        return {
            "valid":      True,
            "tokens":     tokens,
            "traduccion": traduccion,
            "oraciones":  n_oraciones,
            "error":      None,
        }
    except (ValueError, SyntaxError) as ex:
        return {
            "valid":      False,
            "tokens":     [],
            "traduccion": "",
            "oraciones":  0,
            "error":      str(ex),
        }


if __name__ == "__main__":
    pruebas = [
        ("in jaw ixim .",              True,  "Yo como maiz."),
        ("at tz'ok tuj tnam .",        True,  "Tu hablas el pueblo."),
        ("mi e jaw ixim .",            True,  "No el/ella come maiz."),
        ("oj xnaq'tzb'il ali .",       True,  "Nosotros ensenamos nina."),
        ("e b'ixan tuj b'ix .",        True,  "El/ella canta la cancion."),
        ("in jaw ixim . at b'et tuj ja .", True, "Yo como maiz. Tu vas la casa."),
        ("hello world .",              False, None),
        ("in ixim .",                  False, None),
    ]
    print("=== Parser Mam (Maya de Guatemala - Huehuetenango/San Marcos) ===\n")
    ok = err = 0
    for texto, esperado_valid, esperado_trad in pruebas:
        r = parse_mam(texto)
        estado = "VALIDO" if r["valid"] else "INVALIDO"
        correcto = r["valid"] == esperado_valid
        marca = "OK" if correcto else "FALLO"
        print(f"[{marca}] {texto}")
        print(f"       Estado: {estado}")
        if r["valid"]:
            print(f"       Espanol: {r['traduccion']}")
        else:
            print(f"       Error: {r['error']}")
        print()
        if correcto: ok += 1
        else: err += 1
    print(f"Resultado: {ok} correctos, {err} fallidos")