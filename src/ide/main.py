
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import sys, os, io, tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.parsers.mam_parser      import parse_mam
from src.parsers.cow_parser      import parse_cow
from src.parsers.messi_parser    import parse_messi
from src.parsers.chocolat_parser import parse_chocolat
from src.yalex.nfa  import build_nfa
from src.yalex.dfa  import nfa_to_dfa, minimize_dfa
from src.yapar.spec_reader  import load_yapar, Production
from src.yapar.first_follow import compute_first, compute_follow
from src.yapar.lr0          import LR0Automaton
from src.yapar.tables       import build_slr1_table, build_ll1_table, parse_slr1_tree
from src.yapar.lalr         import build_lalr_table, parse_lalr
from src.yapar.parse_tree   import ParseNode
from src.yapar.parallel     import ParallelParser
from src.visualizer import nfa_to_dot, dfa_to_dot, lr0_to_dot, render_to_png, parse_tree_to_dot

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

# Paleta
BG, TOPBAR, PANEL = "#1e1e2e", "#313244", "#181825"
FG, GREEN, BLUE   = "#cdd6f4", "#a6e3a1", "#89b4fa"
PEACH, PURPLE     = "#fab387", "#cba6f7"
RED, YELLOW       = "#f38ba8", "#f9e2af"
FONT, MONO        = ("Consolas", 11), ("Consolas", 12)

PARSERS = {"Mam": parse_mam, "COW": parse_cow,
           "MessiScript": parse_messi, "ChocolaT": parse_chocolat}
HINTS = {
    "Mam":         "in jaw ixim . at b'et tuj ja .",
    "COW":         "moO moO moO Moo",
    "MessiScript": "La agarra Messi. Va Messi, dando clases. Juega Messi. Le pega Messi.",
    "ChocolaT":    "cacao\n  siembra x = 5\n  cosecha x\nkakaw",
    "Regex":       "[a-z]+",
    ".yapar":      "%token ID PLUS TIMES\n\n%%\n\nexpr : expr PLUS term | term ;\nterm : term TIMES factor | factor ;\nfactor : ID ;\n",
}

DEMO_PRODS = [
    Production("expr", ["expr", "PLUS", "term"]),
    Production("expr", ["term"]),
    Production("term", ["term", "TIMES", "factor"]),
    Production("term", ["factor"]),
    Production("factor", ["ID"]),
]
DEMO_TERMS = ["PLUS", "TIMES", "ID"]
DEMO_START = "expr"

AMBIG_PRODS = [
    Production("E", ["E", "PLUS",  "E"]),
    Production("E", ["E", "TIMES", "E"]),
    Production("E", ["ID"]),
]
AMBIG_TERMS = ["PLUS", "TIMES", "ID"]
AMBIG_START = "E"

GRAMMAR_PRESETS = {
    "calculadora": (DEMO_PRODS, DEMO_TERMS, DEMO_START,
                    HINTS[".yapar"]),
    "ambigua E+E|E*E|id": (AMBIG_PRODS, AMBIG_TERMS, AMBIG_START,
                            "%token ID PLUS TIMES\n\n%%\n\nE : E PLUS E | E TIMES E | ID ;\n"),
}

EXT_LANG = {".messi":"MessiScript", ".mam":"Mam", ".cow":"COW",
            ".choc":"ChocolaT", ".chocolat":"ChocolaT"}
CONTENT_LANG = [
    ("la agarra messi", "MessiScript"), ("le pega messi", "MessiScript"),
    ("moo moo", "COW"), ("moo moo", "COW"),
    ("cacao", "ChocolaT"),
    ("in jaw", "Mam"), ("at b'et", "Mam"),
]


# ── AutomataPanel ─────────────────────────────────────────────────────────────
class AutomataPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=PANEL, **kw)
        self._img = self._png = None
        self._scale = 1.0
        hbar = tk.Scrollbar(self, orient=tk.HORIZONTAL)
        vbar = tk.Scrollbar(self, orient=tk.VERTICAL)
        self.cv = tk.Canvas(self, bg=PANEL, relief=tk.FLAT,
                            highlightthickness=0,
                            xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.config(command=self.cv.xview)
        vbar.config(command=self.cv.yview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar.pack(side=tk.RIGHT,  fill=tk.Y)
        self.cv.pack(fill=tk.BOTH, expand=True)
        ctrl = tk.Frame(self, bg=TOPBAR)
        ctrl.place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=5)
        for txt, d in [("+", .25), ("-", -.25), ("1:1", 0)]:
            tk.Button(ctrl, text=txt, width=3,
                      command=lambda v=d: self._zoom(v),
                      bg="#45475a", fg=FG, relief=tk.FLAT, font=FONT
                      ).pack(side=tk.LEFT, padx=1)
        self.cv.create_text(500, 250,
            text="Escribe un patron regex o carga un .yapar\ny presiona los botones de la barra",
            fill="#585b70", font=("Consolas", 12), justify=tk.CENTER)

    def show(self, png_bytes):
        self._png = png_bytes; self._scale = 1.0
        self.update_idletasks(); self._render()

    def _zoom(self, d):
        if not self._png: return
        self._scale = 1.0 if d == 0 else max(.15, min(5., self._scale + d))
        self._render()

    def _render(self):
        if not PIL_OK or not self._png: return
        img = Image.open(io.BytesIO(self._png))
        w, h = max(1, int(img.width*self._scale)), max(1, int(img.height*self._scale))
        img = img.resize((w, h), Image.LANCZOS)
        self._img = ImageTk.PhotoImage(img)
        self.cv.delete("all")
        self.cv.create_image(4, 4, anchor="nw", image=self._img)
        self.cv.configure(scrollregion=(0, 0, w+8, h+8))


class TablePanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=PANEL, **kw)
        self.info = tk.Label(self, text="Carga un .yapar en el editor y presiona SLR(1), LALR o LL(1)",
                             bg=PANEL, fg="#585b70", font=("Consolas", 10), anchor=tk.W)
        self.info.pack(fill=tk.X, padx=4, pady=2)
        frame = tk.Frame(self, bg=PANEL)
        frame.pack(fill=tk.BOTH, expand=True)
        self.tv = ttk.Treeview(frame, show="headings")
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL,   command=self.tv.yview)
        hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.tv.xview)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tv.pack(fill=tk.BOTH, expand=True)
        self.tv.tag_configure("conflict", background="#45172a", foreground=RED)
        self.tv.tag_configure("accept",   background="#1a3020", foreground=GREEN)
        self.tv.tag_configure("shift",    background="#1a2540", foreground=BLUE)
        self.tv.tag_configure("reduce",   background="#2a2010", foreground=YELLOW)

    def load_action_goto(self, action, goto, n_states, terminals,
                         non_terminals, label="", conflicts=None):
        conflict_set = {(c.get("state",-1), c.get("symbol","")) for c in (conflicts or [])}
        terms_s = sorted(terminals) + ["$"]
        nt_s    = sorted(non_terminals)
        cols    = ["Estado"] + terms_s + nt_s
        self.tv.delete(*self.tv.get_children())
        self.tv["columns"] = cols
        for col in cols:
            self.tv.heading(col, text=col)
            self.tv.column(col, width=65, minwidth=45, anchor=tk.CENTER)
        self.tv.column("Estado", width=55)
        nc = len(conflicts) if conflicts else 0
        self.info.config(text=f"{label}  |  {n_states} estados  |  {nc} conflicto(s)", fg=BLUE)
        for sid in range(n_states):
            row, rtag = [str(sid)], ""
            for t in terms_s:
                cell = action.get((sid, t))
                if cell:
                    act, val = cell
                    s   = f"s{val}" if act=="shift" else ("acc" if act=="accept" else f"r{val}")
                    tag = "shift" if act=="shift" else ("accept" if act=="accept" else "reduce")
                    if (sid, t) in conflict_set: tag = "conflict"
                    if not rtag: rtag = tag
                else: s = ""
                row.append(s)
            for nt in nt_s:
                row.append(str(goto.get((sid, nt), "")))
            self.tv.insert("", tk.END, values=row, tags=(rtag or "reduce",))

    def load_ll1(self, table, terminals, non_terminals,
                 productions, label="", conflicts=None):
        conflict_set = {(c.get("non_terminal",""), c.get("terminal","")) for c in (conflicts or [])}
        terms_s = sorted(terminals)
        nt_s    = sorted(non_terminals)
        cols    = ["NT"] + terms_s
        self.tv.delete(*self.tv.get_children())
        self.tv["columns"] = cols
        for col in cols:
            self.tv.heading(col, text=col)
            self.tv.column(col, width=90, minwidth=60, anchor=tk.CENTER)
        self.tv.column("NT", width=80)
        nc = len(conflicts) if conflicts else 0
        self.info.config(text=f"{label}  |  {nc} conflicto(s)", fg=BLUE)
        for nt in nt_s:
            row, rtag = [nt], "shift"
            for t in terms_s:
                prod = table.get((nt, t))
                if prod:
                    body = " ".join(prod.body) if prod.body else "eps"
                    s    = f"{prod.head}>{body}"
                    if (nt, t) in conflict_set: rtag = "conflict"
                else: s = ""
                row.append(s)
            self.tv.insert("", tk.END, values=row, tags=(rtag,))


class StepsPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=PANEL, **kw)
        cols = ["#", "Stack", "Entrada restante", "Accion"]
        self.tv = ttk.Treeview(self, columns=cols, show="headings")
        for col, w in zip(cols, [40, 320, 260, 120]):
            self.tv.heading(col, text=col)
            self.tv.column(col, width=w, anchor=tk.W)
        vsb = ttk.Scrollbar(self, command=self.tv.yview)
        hsb = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tv.xview)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tv.pack(fill=tk.BOTH, expand=True)

    def load(self, steps):
        self.tv.delete(*self.tv.get_children())
        for i, s in enumerate(steps, 1):
            self.tv.insert("", tk.END, values=[
                i,
                " ".join(str(x) for x in s.get("stack", [])),
                " ".join(s.get("input", [])),
                s.get("action", ""),
            ])


class IDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YALex/YAPar IDE  —  Disenyo de Lenguajes  (Dragon Book: Aho, Sethi, Ullman)")
        self.geometry("1400x840")
        self.configure(bg=BG)
        self._prods = DEMO_PRODS
        self._terms = DEMO_TERMS
        self._start = DEMO_START
        self._build()

    def _btn(self, parent, text, cmd, color, padx=8):
        return tk.Button(parent, text=text, command=cmd, bg=color,
                         fg=BG, font=("Consolas", 10, "bold"),
                         relief=tk.FLAT, padx=padx)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build(self):
        self._topbar()
        self._mainpanel()
        self.status = tk.Label(self, text="Listo.  |  Escribe o carga un archivo en el editor.",
                               bg=TOPBAR, fg=GREEN, font=("Consolas", 10), anchor=tk.W)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)
        self._hint()

    def _topbar(self):
        top = tk.Frame(self, bg=TOPBAR, pady=5)
        top.pack(fill=tk.X)
        row = tk.Frame(top, bg=TOPBAR)
        row.pack(fill=tk.X, padx=8)

        sep = lambda: tk.Label(row, text=" | ", bg=TOPBAR,
                               fg="#585b70", font=("Consolas",13)).pack(side=tk.LEFT)

        # Lenguaje natural
        tk.Label(row, text="Lenguaje:", bg=TOPBAR, fg=FG, font=FONT).pack(side=tk.LEFT)
        self.lang = tk.StringVar(value="Mam")
        cb = ttk.Combobox(row, textvariable=self.lang,
                          values=list(PARSERS.keys()) + ["Regex", ".yapar"],
                          state="readonly", width=13)
        cb.pack(side=tk.LEFT, padx=(4,6))
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_lang_change())
        for t, c, col in [("Analizar", self._run,     GREEN),
                           ("Abrir",    self._open,    BLUE),
                           ("Limpiar",  self._limpiar, RED)]:
            self._btn(row, t, c, col).pack(side=tk.LEFT, padx=2)

        sep()

        # YALex — NFA / DFA (usan el patron del editor)
        tk.Label(row, text="YALex:", bg=TOPBAR, fg=FG, font=FONT).pack(side=tk.LEFT)
        for t, c in [("NFA", self._show_nfa), ("DFA", self._show_dfa),
                     ("DFA min", self._show_min_dfa)]:
            self._btn(row, t, c, PEACH).pack(side=tk.LEFT, padx=2)

        sep()

        # YAPar — tablas y automata (usan el .yapar del editor)
        tk.Label(row, text="YAPar:", bg=TOPBAR, fg=FG, font=FONT).pack(side=tk.LEFT)
        for t, c in [("LR(0)",  self._show_lr0),
                     ("SLR(1)", self._show_slr1),
                     ("LALR",   self._show_lalr),
                     ("LL(1)",  self._show_ll1)]:
            self._btn(row, t, c, PURPLE).pack(side=tk.LEFT, padx=2)

        sep()
        self._btn(row, "Arbol + Pasos", self._show_tree, GREEN, padx=10
                  ).pack(side=tk.LEFT, padx=2)
        self._btn(row, "Paralelo", self._show_parallel, YELLOW, padx=10
                  ).pack(side=tk.LEFT, padx=2)

        # Preset de gramatica
        tk.Label(row, text="  Preset:", bg=TOPBAR, fg=FG, font=FONT).pack(side=tk.LEFT)
        self._preset_var = tk.StringVar(value="calculadora")
        preset_cb = ttk.Combobox(row, textvariable=self._preset_var,
                                 values=list(GRAMMAR_PRESETS.keys()),
                                 state="readonly", width=20)
        preset_cb.pack(side=tk.LEFT, padx=(2,0))
        preset_cb.bind("<<ComboboxSelected>>", lambda e: self._load_preset())

    def _mainpanel(self):
        pw = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=BG, sashwidth=5)
        pw.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Editor
        lf = tk.Frame(pw, bg=BG)
        # Indicador de modo
        self._mode_lbl = tk.Label(lf, text="Entrada", bg=BG, fg=BLUE,
                                   font=("Consolas",10,"bold"))
        self._mode_lbl.pack(anchor=tk.W, padx=2)
        self.ed = scrolledtext.ScrolledText(
            lf, font=MONO, bg=PANEL, fg=FG,
            insertbackground=FG, relief=tk.FLAT, wrap=tk.WORD)
        self.ed.pack(fill=tk.BOTH, expand=True)
        pw.add(lf, width=420)

        # Tabs
        rf = tk.Frame(pw, bg=BG)
        nb = ttk.Notebook(rf)
        nb.pack(fill=tk.BOTH, expand=True)
        self.nb = nb

        def text_tab(label, color):
            fr = tk.Frame(nb, bg=BG)
            st = scrolledtext.ScrolledText(fr, font=FONT, bg=PANEL, fg=color,
                                           relief=tk.FLAT, state=tk.DISABLED)
            st.pack(fill=tk.BOTH, expand=True)
            nb.add(fr, text=label)
            return st, fr

        self.tok_w,  self._fr_tok  = text_tab("Tokens",      GREEN)
        self.res_w,  self._fr_res  = text_tab("Resultado",    YELLOW)
        self.trad_w, self._fr_trad = text_tab("Traduccion",   PURPLE)
        self.ff_w,   self._fr_ff   = text_tab("FIRST/FOLLOW", PEACH)

        fr_tabla = tk.Frame(nb, bg=BG)
        self.tabla_panel = TablePanel(fr_tabla)
        self.tabla_panel.pack(fill=tk.BOTH, expand=True)
        nb.add(fr_tabla, text="Tabla")
        self._fr_tabla = fr_tabla

        fr_steps = tk.Frame(nb, bg=BG)
        self.steps_panel = StepsPanel(fr_steps)
        self.steps_panel.pack(fill=tk.BOTH, expand=True)
        nb.add(fr_steps, text="Pasos")
        self._fr_steps = fr_steps

        fr_aut = tk.Frame(nb, bg=BG)
        self.aut_panel = AutomataPanel(fr_aut)
        self.aut_panel.pack(fill=tk.BOTH, expand=True)
        nb.add(fr_aut, text="Automata")
        self._fr_aut = fr_aut

        pw.add(rf)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _editor_text(self):
        return self.ed.get("1.0", tk.END).strip()

    def _hint(self, *_):
        """Carga el ejemplo del lenguaje actual en el editor."""
        lang = self.lang.get()
        self.ed.delete("1.0", tk.END)
        self.ed.insert("1.0", HINTS.get(lang, ""))
        self._update_mode_label()

    def _limpiar(self, *_):
        """Limpia el editor Y todos los paneles de salida."""
        # 1. Editor
        self._hint()
        # 2. Paneles de texto
        for w in (self.tok_w, self.res_w, self.trad_w, self.ff_w):
            w.configure(state=tk.NORMAL)
            w.delete("1.0", tk.END)
            w.configure(state=tk.DISABLED)
        # 3. Tabla
        self.tabla_panel.tv.delete(*self.tabla_panel.tv.get_children())
        self.tabla_panel.info.config(
            text="Carga un .yapar en el editor y presiona SLR(1), LALR o LL(1)",
            fg="#585b70")
        # 4. Pasos
        self.steps_panel.tv.delete(*self.steps_panel.tv.get_children())
        # 5. Automata
        self.aut_panel.cv.delete("all")
        self.aut_panel._png = None
        self.aut_panel.cv.create_text(
            500, 250,
            text="Escribe un patron regex o carga un .yapar\ny presiona los botones de la barra",
            fill="#585b70", font=("Consolas", 12), justify=tk.CENTER)
        # 6. Status
        self._ok(f"Limpiado  —  lenguaje: {self.lang.get()}")

    def _on_lang_change(self):
        """Al cambiar lenguaje: limpiar todo y cargar el ejemplo del nuevo lenguaje."""
        self._limpiar()

    def _update_mode_label(self):
        lang = self.lang.get()
        labels = {
            "Regex":  "Patron regex  (para NFA / DFA / DFA min)",
            ".yapar": "Gramatica .yapar  (para LR(0) / SLR(1) / LALR / LL(1) / Arbol)",
        }
        self._mode_lbl.config(
            text=labels.get(lang, f"Entrada  [{lang}]")
        )

    def _open(self):
        path = filedialog.askopenfilename(filetypes=[
            ("Todos","*.*"),("Messi","*.messi"),("YAL","*.yal"),
            ("YAPar","*.yapar"),("COW","*.cow"),("Mam","*.mam")])
        if not path: return
        content = open(path, encoding="utf-8-sig").read()
        self.ed.delete("1.0", tk.END)
        self.ed.insert("1.0", content)

        # Auto-detectar lenguaje
        ext = os.path.splitext(path)[1].lower()
        if ext in EXT_LANG:
            self.lang.set(EXT_LANG[ext])
        elif ext in (".yapar", ".yp"):
            self.lang.set(".yapar")
        elif ext in (".yal", ".l"):
            self.lang.set("Regex")
        else:
            preview = content[:500].lower()
            for kw, lg in CONTENT_LANG:
                if kw in preview:
                    self.lang.set(lg); break
            else:
                if "%%" in content:
                    self.lang.set(".yapar")

        self._update_mode_label()
        self._ok(f"{os.path.basename(path)}  →  {self.lang.get()}")

    def _set(self, w, text):
        w.configure(state=tk.NORMAL); w.delete("1.0", tk.END)
        w.insert(tk.END, text); w.configure(state=tk.DISABLED)

    def _ok(self, msg):  self.status.config(text=msg, fg=GREEN)
    def _err(self, msg): self.status.config(text=msg, fg=RED)

    def _is_yal(self, txt):
        """Detecta si el contenido del editor es un archivo .yal."""
        return "rule " in txt or ("let " in txt and "=" in txt)

    def _get_regex(self):
        """
        Obtiene el patron regex DEL EDITOR.
        Si el editor tiene un .yal, devuelve None con instrucciones.
        """
        txt = self._editor_text()
        if not txt:
            return None, "El editor esta vacio.\nEscribe un patron regex (ej: [a-z]+) o carga un .yal"
        if "%%" in txt:
            return None, "El editor tiene un .yapar. Para NFA/DFA:\n  • Escribe un patron regex en el editor, o\n  • Carga un archivo .yal"
        if self._is_yal(txt):
            return None, "El editor tiene un .yal.\nPresiona NFA para ver el automata de todas sus reglas combinadas."
        if len(txt.splitlines()) > 5:
            return None, "El editor tiene varias lineas.\nPara NFA/DFA escribe un patron simple (ej: [a-z]+) o carga un .yal"
        return txt.strip(), None

    def _build_nfa_from_yal(self):
        """
        Construye un NFA combinado desde un archivo .yal en el editor.
        Devuelve (nfa, titulo) o lanza excepcion.
        """
        from src.yalex.spec_reader import load_yal
        from src.yalex.nfa import build_nfa, NFA, EPSILON
        txt = self._editor_text()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yal",
                                         delete=False, encoding="utf-8") as f:
            f.write(txt); tmp = f.name
        try:
            spec = load_yal(tmp)
        finally:
            os.unlink(tmp)

        # Construir NFA para cada regla y combinarlos
        combined = NFA()
        new_start = combined.new_state()
        n_rules = 0
        errors = []
        for rule in spec.rules:
            try:
                expanded = spec.expand_lets(rule.pattern)
                nfa = build_nfa(expanded, token_name=rule.action[:20] or "TOKEN")
                # Reusar estados del NFA individual en el combinado
                for state in nfa.states:
                    state.id += combined._counter
                    combined.states.append(state)
                combined._counter += len(nfa.states)
                nfa.accept.is_accept = True
                new_start.add(EPSILON, nfa.start)
                n_rules += 1
            except Exception as e:
                errors.append(f"Regla '{rule.pattern[:30]}': {e}")

        if n_rules == 0:
            raise ValueError("No se pudo construir NFA para ninguna regla.\n" + "\n".join(errors))

        combined.start = new_start
        titulo = f".yal — {n_rules} regla(s)"
        if errors:
            titulo += f" ({len(errors)} error(es))"
        return combined, titulo, errors

    def _load_grammar(self):
        """Lee gramatica del editor (si tiene %%) o usa la ultima cargada."""
        txt = self._editor_text()
        if "%%" in txt:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yapar",
                                             delete=False, encoding="utf-8") as f:
                f.write(txt); tmp = f.name
            spec = load_yapar(tmp)
            os.unlink(tmp)
            self._prods = spec.productions
            self._terms = spec.tokens
            self._start = spec.start_symbol
        return self._prods, self._terms, self._start

    def _load_preset(self):
        name = self._preset_var.get()
        if name in GRAMMAR_PRESETS:
            prods, terms, start, yapar_text = GRAMMAR_PRESETS[name]
            self._prods = prods; self._terms = terms; self._start = start
            self.ed.delete("1.0", tk.END)
            self.ed.insert("1.0", yapar_text)
            self.lang.set(".yapar")
            self._update_mode_label()
            self._ok(f"Preset cargado: {name}")

    # ── Analizador de lenguajes ───────────────────────────────────────────────
    def _run(self):
        txt  = self._editor_text()
        lang = self.lang.get()
        if lang not in PARSERS:
            self._err(f"Selecciona Mam, COW, MessiScript o ChocolaT para Analizar")
            return
        r    = PARSERS[lang](txt)
        toks = r.get("tokens", [])
        self._set(self.tok_w, "\n".join(str(t) for t in toks) if toks else "(sin tokens)")
        estado = "VALIDO" if r.get("valid") else "INVALIDO"
        parts  = [f"Lenguaje: {lang}", f"Estado:   {estado}"]
        if r.get("error"):       parts.append("Error:    " + r["error"])
        if r.get("output"):      parts.append("Output:   " + str(r["output"]))
        if r.get("oraciones"):   parts.append("Oraciones:" + str(r["oraciones"]))
        if r.get("token_count"): parts.append("Tokens:   " + str(r["token_count"]))
        if r.get("estadisticas"):
            parts.append("\nComandos:")
            for k,v in sorted(r["estadisticas"].items()):
                parts.append(f"  {k:15} {v}")
        self._set(self.res_w, "\n".join(parts))
        self._set(self.trad_w, r.get("traduccion") or "(no disponible)")
        self.nb.select(self._fr_tok)
        if r.get("valid"): self._ok(f"VALIDO — {lang}")
        else:               self._err(f"INVALIDO — {r.get('error','')}")

    # ── FIRST/FOLLOW ──────────────────────────────────────────────────────────
    def _show_ff(self, prods, terms, start):
        first  = compute_first(prods, set(terms))
        follow = compute_follow(prods, start, first)
        nt     = {p.head for p in prods}
        lines  = [f"Gramatica: {start}  ({len(prods)} producciones)", "",
                  "Dragon Book Alg 4.4 — FIRST", ""]
        for s in sorted(nt):
            lines.append(f"  FIRST({s:12}) = {{ {', '.join(sorted(first.get(s,set())))} }}")
        lines += ["", "Dragon Book Alg 4.5 — FOLLOW", ""]
        for s in sorted(nt):
            lines.append(f"  FOLLOW({s:11}) = {{ {', '.join(sorted(follow.get(s,set())))} }}")
        self._set(self.ff_w, "\n".join(lines))

    # ── Tablas parser ─────────────────────────────────────────────────────────
    def _show_slr1(self):
        try:
            prods, terms, start = self._load_grammar()
            r   = build_slr1_table(prods, terms, start)
            lr0 = r["lr0"]
            nt  = {p.head for p in prods}
            self.tabla_panel.load_action_goto(
                r["action"], r["goto"], len(lr0.states), set(terms), nt,
                label=f"SLR(1)  [Alg 4.8]  —  {start}",
                conflicts=r["conflicts"])
            self._show_ff(prods, terms, start)
            self.nb.select(self._fr_tabla)
            self._ok(f"SLR(1): {len(lr0.states)} estados, {len(r['conflicts'])} conflicto(s)  [gramatica: {start}]")
        except Exception as ex:
            self._err(f"SLR(1) error: {ex}"); messagebox.showerror("SLR(1)", str(ex))

    def _show_lalr(self):
        try:
            prods, terms, start = self._load_grammar()
            r   = build_lalr_table(prods, terms, start)
            lr0 = r["lr0"]
            nt  = {p.head for p in prods}
            self.tabla_panel.load_action_goto(
                r["action"], r["goto"], len(lr0.states), set(terms), nt,
                label=f"LALR  [Alg 4.62]  —  {start}",
                conflicts=r["conflicts"])
            self.nb.select(self._fr_tabla)
            self._ok(f"LALR: {len(lr0.states)} estados, {len(r['conflicts'])} conflicto(s)  [gramatica: {start}]")
        except Exception as ex:
            self._err(f"LALR error: {ex}"); messagebox.showerror("LALR", str(ex))

    def _show_ll1(self):
        try:
            prods, terms, start = self._load_grammar()
            r  = build_ll1_table(prods, terms, start)
            nt = {p.head for p in prods}
            self.tabla_panel.load_ll1(
                r["table"], set(terms), nt, prods,
                label=f"LL(1)  [Sec 4.4]  —  {start}",
                conflicts=r["conflicts"])
            self.nb.select(self._fr_tabla)
            self._ok(f"LL(1): {len(r['conflicts'])} conflicto(s)  [gramatica: {start}]")
        except Exception as ex:
            self._err(f"LL(1) error: {ex}"); messagebox.showerror("LL(1)", str(ex))

    # ── NFA / DFA — leen el patron del editor ─────────────────────────────────
    def _disp_aut(self, png, msg):
        self.nb.select(self._fr_aut); self.update_idletasks()
        self.aut_panel.show(png); self._ok(msg)

    def _show_nfa(self):
        txt = self._editor_text()
        try:
            if self._is_yal(txt):
                # Editor tiene .yal — construir NFA combinado de todas las reglas
                nfa, titulo, errs = self._build_nfa_from_yal()
                self._disp_aut(render_to_png(nfa_to_dot(nfa, f"NFA (Thompson Alg 3.3) — {titulo}")),
                               f"NFA del .yal: {len(nfa.states)} estados")
                if errs:
                    self._err(f"NFA parcial — {len(errs)} regla(s) con error")
            else:
                pat, err = self._get_regex()
                if err: self._err(err); messagebox.showinfo("NFA — como usar", err); return
                nfa = build_nfa(pat, token_name="TOKEN")
                self._disp_aut(render_to_png(nfa_to_dot(nfa, f"NFA (Thompson Alg 3.3) — {pat}")),
                               f"NFA para: {pat}  |  {len(nfa.states)} estados")
        except Exception as ex:
            self._err(f"NFA error: {ex}"); messagebox.showerror("NFA", str(ex))

    def _show_dfa(self):
        txt = self._editor_text()
        try:
            if self._is_yal(txt):
                nfa, titulo, errs = self._build_nfa_from_yal()
                dfa = nfa_to_dfa(nfa)
                self._disp_aut(render_to_png(dfa_to_dot(dfa, f"DFA (Subconjuntos Alg 3.7) — {titulo}")),
                               f"DFA del .yal: {len(dfa.states)} estados")
                if errs:
                    self._err(f"DFA parcial — {len(errs)} regla(s) con error")
            else:
                pat, err = self._get_regex()
                if err: self._err(err); messagebox.showinfo("DFA — como usar", err); return
                dfa = nfa_to_dfa(build_nfa(pat, token_name="TOKEN"))
                self._disp_aut(render_to_png(dfa_to_dot(dfa, f"DFA (Subconjuntos Alg 3.7) — {pat}")),
                               f"DFA para: {pat}  |  {len(dfa.states)} estados")
        except Exception as ex:
            self._err(f"DFA error: {ex}"); messagebox.showerror("DFA", str(ex))

    def _show_min_dfa(self):
        txt = self._editor_text()
        try:
            if self._is_yal(txt):
                nfa, titulo, errs = self._build_nfa_from_yal()
                dfa  = nfa_to_dfa(nfa)
                mdfa = minimize_dfa(dfa)
                self._disp_aut(render_to_png(dfa_to_dot(mdfa, f"DFA min (Hopcroft Alg 3.39) — {titulo}")),
                               f"DFA min del .yal: {len(dfa.states)} -> {len(mdfa.states)} estados")
                if errs:
                    self._err(f"DFA min parcial — {len(errs)} regla(s) con error")
            else:
                pat, err = self._get_regex()
                if err: self._err(err); messagebox.showinfo("DFA min — como usar", err); return
                nfa  = build_nfa(pat, token_name="TOKEN")
                dfa  = nfa_to_dfa(nfa)
                mdfa = minimize_dfa(dfa)
                self._disp_aut(render_to_png(dfa_to_dot(mdfa, f"DFA min (Hopcroft Alg 3.39) — {pat}")),
                               f"DFA min para: {pat}  |  {len(dfa.states)}->{len(mdfa.states)} estados")
        except Exception as ex:
            self._err(f"DFA min error: {ex}"); messagebox.showerror("DFA min", str(ex))

    def _show_lr0(self):
        try:
            prods, terms, start = self._load_grammar()
            lr0 = LR0Automaton(prods, start)
            self._disp_aut(render_to_png(lr0_to_dot(lr0, f"LR(0) (Alg 4.7) — {start}")),
                           f"LR(0): {len(lr0.states)} estados, {len(lr0.conflicts)} conflicto(s)  [gramatica: {start}]")
        except Exception as ex:
            self._err(f"LR(0) error: {ex}"); messagebox.showerror("LR(0)", str(ex))

    # ── Arbol + Pasos ─────────────────────────────────────────────────────────
    def _show_tree(self):
        try:
            prods, terms, start = self._load_grammar()
        except Exception as ex:
            self._err(f"Error cargando gramatica: {ex}"); return

        # Construir un ejemplo valido: buscar un terminal de tipo "id/num"
        # y usarlo en una expresion simple
        def _default_tokens(terms_list):
            """Genera un ejemplo de cadena valida para la gramatica."""
            atoms = [t for t in terms_list
                     if t.upper() in ("ID","NUM","IDENTIFIER","VAR","NAME","A","B","X","Y")]
            atom = atoms[0] if atoms else (terms_list[0] if terms_list else "ID")
            # Buscar un operador binario
            ops = [t for t in terms_list
                   if t.upper() in ("PLUS","MINUS","TIMES","DIV","ADD","SUB","MUL","+","-","*","/")]
            if ops:
                return f"{atom} {ops[0]} {atom}"
            return atom

        dlg = tk.Toplevel(self)
        dlg.title("Arbol de Derivacion — " + start)
        dlg.configure(bg=BG); dlg.geometry("580x155"); dlg.resizable(False,False)
        tk.Label(dlg, text=f"Tokens de la gramatica '{start}' separados por espacio:",
                 bg=BG, fg=FG, font=FONT).pack(pady=(12,4))
        available = "  Tokens disponibles: " + ", ".join(sorted(terms))
        tk.Label(dlg, text=available, bg=BG, fg="#585b70", font=("Consolas",9)).pack()
        tk.Label(dlg, text="  (edita la cadena — cada palabra debe ser un token declarado en %token)",
                 bg=BG, fg="#585b70", font=("Consolas",9)).pack()
        ev = tk.StringVar(value=_default_tokens(sorted(terms)))
        tk.Entry(dlg, textvariable=ev, width=50, font=FONT, bg=PANEL, fg=FG,
                 insertbackground=FG, relief=tk.FLAT).pack(padx=16, pady=4)

        def _parse():
            raw = ev.get().strip().split()
            tlist = [(t,t) for t in raw]; dlg.destroy()
            try:
                r = build_slr1_table(prods, terms, start)
                steps, tree = parse_slr1_tree(tlist, r["action"], r["goto"], prods)
                self.steps_panel.load(steps)
                self.nb.select(self._fr_steps); self.update_idletasks()
                dot = parse_tree_to_dot(tree, title="Arbol — " + " ".join(raw))
                self.nb.select(self._fr_aut); self.update_idletasks()
                self.aut_panel.show(render_to_png(dot))
                self._ok(f"Arbol: {len(steps)} pasos  |  tokens: {' '.join(raw)}")
            except SyntaxError as e:
                self._err(f"Error: {e}"); messagebox.showerror("Error de parseo", str(e))
            except Exception as e:
                self._err(f"Error: {e}"); messagebox.showerror("Error", str(e))

        tk.Button(dlg, text="Parsear", command=_parse,
                  bg=GREEN, fg=BG, font=("Consolas",11,"bold"),
                  relief=tk.FLAT, padx=16).pack(pady=6)

    # ── Parser Paralelo ───────────────────────────────────────────────────────
    def _show_parallel(self):
        try:
            prods, terms, start = self._load_grammar()
            r_slr = build_slr1_table(prods, terms, start)
            n_conflicts = len(r_slr["conflicts"])
        except Exception as ex:
            self._err(f"Error cargando gramatica: {ex}"); return

        dlg = tk.Toplevel(self)
        dlg.title("Parser Paralelo — Resolucion de Conflictos Shift/Reduce")
        dlg.configure(bg=BG); dlg.geometry("940x620")

        hdr = tk.Frame(dlg, bg=TOPBAR, pady=6)
        hdr.pack(fill=tk.X)
        color_hdr = RED if n_conflicts else GREEN
        tk.Label(hdr, text=f"Gramatica: {start}   |   {n_conflicts} conflicto(s) shift/reduce",
                 bg=TOPBAR, fg=color_hdr, font=("Consolas",11,"bold")).pack(side=tk.LEFT, padx=10)
        if n_conflicts == 0:
            tk.Label(hdr, text="(sin conflictos — el parser ira directo)",
                     bg=TOPBAR, fg="#585b70", font=FONT).pack(side=tk.LEFT)

        def _default_tokens(terms_list):
            atoms = [t for t in terms_list
                     if t.upper() in ("ID","NUM","IDENTIFIER","VAR","NAME","A","B","X","Y")]
            atom = atoms[0] if atoms else (terms_list[0] if terms_list else "ID")
            ops  = [t for t in terms_list
                    if t.upper() in ("PLUS","MINUS","TIMES","DIV","ADD","SUB","MUL","+","-","*","/")]
            if ops:
                return f"{atom} {ops[0]} {atom} {ops[-1]} {atom}"
            return atom

        ev = tk.StringVar(value=_default_tokens(sorted(terms)))
        input_frame = tk.Frame(dlg, bg=BG, pady=4)
        input_frame.pack(fill=tk.X, padx=8)
        tk.Label(input_frame, text="Tokens:", bg=BG, fg=FG, font=FONT).pack(side=tk.LEFT)
        tk.Entry(input_frame, textvariable=ev, width=48,
                 font=FONT, bg=PANEL, fg=FG, insertbackground=FG,
                 relief=tk.FLAT).pack(side=tk.LEFT, padx=(6,8))
        tk.Button(input_frame, text="Analizar", command=lambda: _run(),
                  bg=YELLOW, fg=BG, font=("Consolas",10,"bold"),
                  relief=tk.FLAT, padx=10).pack(side=tk.LEFT)

        cols_frame = tk.Frame(dlg, bg=BG)
        cols_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        def make_col(parent, label, color):
            fr = tk.Frame(parent, bg=BG)
            fr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3)
            tk.Label(fr, text=label, bg=BG, fg=color,
                     font=("Consolas",11,"bold")).pack(anchor=tk.W)
            st = scrolledtext.ScrolledText(fr, font=("Consolas",9),
                                           bg=PANEL, fg=color,
                                           relief=tk.FLAT, state=tk.DISABLED)
            st.pack(fill=tk.BOTH, expand=True)
            return st

        col_pre    = make_col(cols_frame, "Antes del conflicto", FG)
        col_shift  = make_col(cols_frame, "Camino  SHIFT",  BLUE)
        col_reduce = make_col(cols_frame, "Camino  REDUCE", PEACH)

        status_lbl = tk.Label(dlg, text="", bg=TOPBAR, fg=GREEN,
                              font=("Consolas",10), anchor=tk.W)
        status_lbl.pack(fill=tk.X, side=tk.BOTTOM)

        def _setw(w, text, fg=None):
            w.configure(state=tk.NORMAL); w.delete("1.0", tk.END)
            w.insert(tk.END, text)
            if fg: w.configure(fg=fg)
            w.configure(state=tk.DISABLED)

        def _fmt(steps):
            if not steps: return "(sin pasos)"
            lines = []
            for i, s in enumerate(steps, 1):
                st = " ".join(str(x) for x in s.get("stack",[]))
                inp = " ".join(s.get("input",[]))
                lines.append(f"{i:>3}. [{st}] | {inp} | {s.get('action','')}")
            return "\n".join(lines)

        def _run():
            raw   = ev.get().strip().split()
            tlist = [(t,t) for t in raw]
            pp    = ParallelParser(r_slr["action"], r_slr["goto"], prods)
            result = pp.parse(tlist)

            pre = _fmt(result.steps_before)
            if result.conflict_at:
                pre += f"\n\nCONFLICTO en estado {result.conflict_at[0]}, simbolo '{result.conflict_at[1]}'"
            _setw(col_pre, pre)

            if result.shift_path:
                sp  = result.shift_path
                txt = ("OK " if sp.success else "FALLO ")
                txt += f"({sp.n_steps} pasos)\n\n" if sp.success else f"\nError: {sp.error}\n\n"
                txt += _fmt(sp.steps)
                _setw(col_shift, txt, GREEN if sp.success else RED)
            else:
                _setw(col_shift, "(camino directo — sin conflicto)")

            if result.reduce_path:
                rp  = result.reduce_path
                txt = ("OK " if rp.success else "FALLO ")
                txt += f"({rp.n_steps} pasos)\n\n" if rp.success else f"\nError: {rp.error}\n\n"
                txt += _fmt(rp.steps)
                _setw(col_reduce, txt, GREEN if rp.success else RED)
            else:
                _setw(col_reduce, "(camino directo — sin conflicto)")

            if result.both_accept:
                msg = f"AMBIGUO — dos derivaciones para: {' '.join(raw)}"
                status_lbl.config(text=msg, fg=YELLOW)
            elif result.success:
                status_lbl.config(text=f"ACEPTADO por camino: {result.winner.upper()}  |  {' '.join(raw)}", fg=GREEN)
            else:
                status_lbl.config(text=f"RECHAZADO — ningún camino acepta  |  {' '.join(raw)}", fg=RED)

        _run()


def main():
    IDE().mainloop()


if __name__ == "__main__":
    main()
