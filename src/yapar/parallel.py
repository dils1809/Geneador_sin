"""
M7 - Paralelismo para resolucion de conflictos shift/reduce

Dragon Book sec 4.8.3 — cuando hay un conflicto shift/reduce en la tabla,
el parser no puede decidir deterministicamente. La solucion paralela:

  Estado actual: stack S, input I, CONFLICTO en (estado, simbolo)
  ┌──────────────────────────────────────┐
  │  Hilo SHIFT  → aplica shift, continua │
  │  Hilo REDUCE → aplica reduce, continua│
  └──────────────────────────────────────┘
       ↓ ambos corren simultaneamente
  El que llega a ACCEPT primero gana.
  Si ambos fallan → cadena invalida.
  Si ambos aceptan → gramatica ambigua (dos derivaciones posibles).

Retorna informacion detallada de AMBOS caminos para visualizacion.
"""

import threading
from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class PathResult:
    """Resultado de un camino de parsing (shift o reduce)."""
    label:    str          # "shift" o "reduce"
    success:  bool
    steps:    list = field(default_factory=list)   # [(stack, input, action), ...]
    tree:     object = None   # ParseNode raiz
    error:    str = ""
    n_steps:  int = 0


@dataclass
class ParallelResult:
    """Resultado completo del parser paralelo."""
    success:      bool
    winner:       str        # "shift", "reduce", "ambos", "ninguno"
    both_accept:  bool       # True si la gramatica es ambigua (dos derivaciones)
    shift_path:   PathResult = None
    reduce_path:  PathResult = None
    conflict_at:  tuple = None   # (estado, simbolo) donde se detecto el conflicto
    steps_before: list = field(default_factory=list)  # pasos antes del conflicto


class ParallelParser:
    """
    Parser LR con resolucion paralela de conflictos shift/reduce.
    Implementa el analisis de caminos alternativos del PDF.
    """

    def __init__(self, action: dict, goto: dict, productions: list):
        self.action      = action
        self.goto        = goto
        self.productions = productions

    def parse(self, tokens: list) -> ParallelResult:
        """
        Parsea una lista de tokens resolviendo conflictos en paralelo.
        tokens: lista de (tipo, lexema)
        """
        input_ = list(tokens) + [("$", "$")]
        stack  = [0]
        steps_before = []
        pos    = 0

        while pos < len(input_):
            state    = stack[-1]
            tok_type = input_[pos][0]
            key      = (state, tok_type)

            # ── Sin entrada en la tabla → cadena invalida ──────────────────
            if key not in self.action:
                return ParallelResult(
                    success=False, winner="ninguno", both_accept=False,
                    steps_before=steps_before,
                    shift_path=PathResult("shift", False, error=f"Error en estado {state} con {tok_type!r}"),
                    reduce_path=PathResult("reduce", False, error=f"Error en estado {state} con {tok_type!r}"),
                )

            act, val = self.action[key]

            # ── Detectar conflicto: ¿hay REDUCE en este estado ademas del SHIFT? ──
            has_reduce_here = any(
                k[0] == state and v[0] == "reduce"
                for k, v in self.action.items()
            )
            has_shift_here = act == "shift"

            if has_shift_here and has_reduce_here:
                # Encontramos un conflicto — lanzar ambos hilos
                return self._resolve_parallel(
                    stack, input_, pos, steps_before, (state, tok_type)
                )

            # ── Sin conflicto: avanzar normalmente ────────────────────────
            steps_before.append({
                "stack":  list(stack),
                "input":  [t[0] for t in input_[pos:]],
                "action": f"{act} {val}",
            })

            if act == "accept":
                return ParallelResult(
                    success=True, winner="directo", both_accept=False,
                    steps_before=steps_before,
                )
            elif act == "shift":
                stack.append(tok_type)
                stack.append(val)
                pos += 1
            elif act == "reduce":
                prod = self.productions[val]
                for _ in range(len(prod.body) * 2):
                    stack.pop()
                nt   = prod.head
                gst  = self.goto.get((stack[-1], nt))
                if gst is None:
                    return ParallelResult(success=False, winner="ninguno",
                                         both_accept=False, steps_before=steps_before)
                stack.append(nt)
                stack.append(gst)

        return ParallelResult(success=False, winner="ninguno", both_accept=False,
                              steps_before=steps_before)

    def _resolve_parallel(self, stack, input_, pos, steps_before, conflict_at):
        """Lanza dos hilos: uno hace SHIFT, otro hace REDUCE."""
        from .parse_tree import ParseNode

        shift_r  = PathResult("shift",  False)
        reduce_r = PathResult("reduce", False)
        lock     = threading.Lock()

        def run_shift():
            act, val = self.action[(conflict_at[0], conflict_at[1])]
            # El camino shift aplica el shift y sigue
            new_stack = list(stack) + [conflict_at[1], val]
            new_input = input_[pos+1:]
            try:
                steps, tree = self._simulate_full(new_stack, new_input)
                with lock:
                    shift_r.success = True
                    shift_r.steps   = steps
                    shift_r.tree    = tree
                    shift_r.n_steps = len(steps)
            except SyntaxError as e:
                with lock:
                    shift_r.error = str(e)

        def run_reduce():
            # El camino reduce aplica la primera reduccion disponible en este estado
            reduce_action = next(
                (v for k, v in self.action.items()
                 if k[0] == conflict_at[0] and v[0] == "reduce"),
                None
            )
            if reduce_action is None:
                with lock:
                    reduce_r.error = "Sin accion reduce disponible"
                return
            new_stack = list(stack)
            prod = self.productions[reduce_action[1]]
            for _ in range(len(prod.body) * 2):
                if new_stack: new_stack.pop()
            nt  = prod.head
            gst = self.goto.get((new_stack[-1] if new_stack else 0, nt))
            if gst is None:
                with lock:
                    reduce_r.error = f"Sin GOTO para ({new_stack[-1] if new_stack else 0}, {nt})"
                return
            new_stack.append(nt)
            new_stack.append(gst)
            try:
                steps, tree = self._simulate_full(new_stack, input_[pos:])
                with lock:
                    reduce_r.success = True
                    reduce_r.steps   = steps
                    reduce_r.tree    = tree
                    reduce_r.n_steps = len(steps)
            except SyntaxError as e:
                with lock:
                    reduce_r.error = str(e)

        t_shift  = threading.Thread(target=run_shift,  daemon=True)
        t_reduce = threading.Thread(target=run_reduce, daemon=True)
        t_shift.start()
        t_reduce.start()
        t_shift.join(timeout=5.0)
        t_reduce.join(timeout=5.0)

        both   = shift_r.success and reduce_r.success
        winner = ("ambos"  if both else
                  "shift"  if shift_r.success else
                  "reduce" if reduce_r.success else
                  "ninguno")

        return ParallelResult(
            success      = shift_r.success or reduce_r.success,
            winner       = winner,
            both_accept  = both,
            shift_path   = shift_r,
            reduce_path  = reduce_r,
            conflict_at  = conflict_at,
            steps_before = steps_before,
        )

    def _simulate_full(self, stack, input_):
        """Simula el parser desde un estado dado. Devuelve (steps, ParseNode)."""
        from .parse_tree import ParseNode
        stack     = list(stack)
        input_    = list(input_) + ([("$","$")] if not input_ or input_[-1][0] != "$" else [])
        sym_stack = []
        steps     = []
        pos       = 0
        MAX       = 500  # limite de pasos para evitar bucles infinitos

        while len(steps) < MAX:
            state    = stack[-1]
            tok_type = input_[pos][0]
            tok_val  = input_[pos][1]
            key      = (state, tok_type)

            if key not in self.action:
                raise SyntaxError(
                    f"Error en estado {state} con token {tok_type!r}"
                )

            act, val = self.action[key]
            steps.append({
                "stack":  list(stack),
                "input":  [t[0] for t in input_[pos:]],
                "action": f"{act} {val}",
            })

            if act == "accept":
                root = sym_stack[-1] if sym_stack else ParseNode("OK", [])
                return steps, root
            elif act == "shift":
                sym_stack.append(ParseNode(tok_type, [], value=tok_val))
                stack.append(tok_type)
                stack.append(val)
                pos += 1
            elif act == "reduce":
                prod = self.productions[val]
                children = []
                for _ in range(len(prod.body)):
                    stack.pop(); stack.pop()
                    if sym_stack: children.insert(0, sym_stack.pop())
                node = ParseNode(prod.head, children)
                sym_stack.append(node)
                gst = self.goto.get((stack[-1], prod.head))
                if gst is None:
                    raise SyntaxError(f"Sin GOTO para ({stack[-1]}, {prod.head})")
                stack.append(prod.head)
                stack.append(gst)

        raise SyntaxError(f"Limite de {MAX} pasos alcanzado — posible bucle")
