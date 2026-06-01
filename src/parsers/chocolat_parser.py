import re
KW = {
    "cacao": "INICIO", "kakaw": "FIN", "siembra": "DECL", "cosecha": "PRINT",
    "si_llueve": "IF", "si_seco": "ELSE", "mientras": "WHILE", "fin": "END",
    "devuelve": "RETURN", "func": "FUNC", "verdad": "TRUE", "mentira": "FALSE",
}

def tokenize_chocolat(text):
    tokens = []
    for ln, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        for p in re.findall(r"[a-zA-Z_]\w*|[0-9]+(?:\.[0-9]+)?|[+\-*/=<>!]=?|[()\[\]{}]", line):
            if p in KW:
                tokens.append((KW[p], p, ln))
            elif re.match(r"^[0-9]+(\.[0-9]+)?$", p):
                tokens.append(("NUM", p, ln))
            elif re.match(r"^[a-zA-Z_]\w*$", p):
                tokens.append(("ID", p, ln))
            else:
                tokens.append(("SYM", p, ln))
    return tokens

def validate_chocolat(tokens):
    tipos = [t for t, _, _ in tokens]
    if not tipos or tipos[0] != "INICIO":
        raise SyntaxError("El programa debe comenzar con 'cacao'")
    if tipos[-1] != "FIN":
        raise SyntaxError("El programa debe terminar con 'kakaw'")
    stack = []
    for tipo, val, ln in tokens:
        if tipo in ("IF", "WHILE", "FUNC"):
            stack.append((tipo, ln))
        elif tipo == "END":
            if not stack:
                raise SyntaxError(f"'fin' sin bloque abierto en linea {ln}")
            stack.pop()
    if stack:
        raise SyntaxError(f"Bloque {stack[-1][0]} sin cerrar con 'fin'")
    return True

def parse_chocolat(text):
    try:
        t = tokenize_chocolat(text)
        validate_chocolat(t)
        return {"valid": True, "tokens": t, "error": None}
    except SyntaxError as ex:
        return {"valid": False, "tokens": [], "error": str(ex)}
