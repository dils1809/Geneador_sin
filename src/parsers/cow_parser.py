COMANDOS = {"moo","MOO","mOo","moO","mOO","MOo","Moo","MoO"}

def tokenize_cow(text):
    tokens = []
    for w in text.split():
        if w in COMANDOS:
            tokens.append(("CMD", w))
        else:
            raise ValueError(f"Comando COW desconocido: {w!r}")
    return tokens

def validate_cow(tokens):
    depth = 0
    for _, cmd in tokens:
        if cmd == "mOO":
            depth += 1
        elif cmd == "MOo":
            depth -= 1
            if depth < 0:
                raise SyntaxError("MOo sin mOO correspondiente")
    if depth != 0:
        raise SyntaxError(f"{depth} mOO sin cerrar")
    return True

def parse_cow(text):
    try:
        t = tokenize_cow(text)
        validate_cow(t)
        return {"valid": True, "tokens": t, "error": None}
    except (ValueError, SyntaxError) as ex:
        return {"valid": False, "tokens": [], "error": str(ex)}
