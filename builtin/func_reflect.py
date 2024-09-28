#!/usr/bin/env python2
"""
func_reflect.py - Functions for reflecting on Oils code - OSH or YSH.
"""
from __future__ import print_function

from _devbuild.gen.runtime_asdl import (scope_e)
from _devbuild.gen.syntax_asdl import source
from _devbuild.gen.value_asdl import (value, value_t)

from core import alloc
from core import error
from core import main_loop
from core import state
from core import vm
from frontend import location
from frontend import reader
from frontend import typed_args
from mycpp.mylib import log
from ysh import expr_eval

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from frontend import parse_lib
    from display import ui

_ = log


class Shvar_get(vm._Callable):
    """Look up with dynamic scope."""

    def __init__(self, mem):
        # type: (state.Mem) -> None
        vm._Callable.__init__(self)
        self.mem = mem

    def Call(self, rd):
        # type: (typed_args.Reader) -> value_t
        name = rd.PosStr()
        rd.Done()
        return state.DynamicGetVar(self.mem, name, scope_e.Dynamic)


class GetVar(vm._Callable):
    """Look up a variable, with normal scoping rules."""

    def __init__(self, mem):
        # type: (state.Mem) -> None
        vm._Callable.__init__(self)
        self.mem = mem

    def Call(self, rd):
        # type: (typed_args.Reader) -> value_t
        name = rd.PosStr()
        rd.Done()
        return state.DynamicGetVar(self.mem, name, scope_e.LocalOrGlobal)


class SetVar(vm._Callable):
    """Set a variable in the local scope.

    We could have a separae setGlobal() too.
    """

    def __init__(self, mem):
        # type: (state.Mem) -> None
        vm._Callable.__init__(self)
        self.mem = mem

    def Call(self, rd):
        # type: (typed_args.Reader) -> value_t
        var_name = rd.PosStr()
        val = rd.PosValue()
        rd.Done()
        self.mem.SetNamed(location.LName(var_name), val, scope_e.LocalOnly)
        return value.Null


class ParseCommand(vm._Callable):

    def __init__(self, parse_ctx, errfmt):
        # type: (parse_lib.ParseContext, ui.ErrorFormatter) -> None
        self.parse_ctx = parse_ctx
        self.errfmt = errfmt

    def Call(self, rd):
        # type: (typed_args.Reader) -> value_t
        code_str = rd.PosStr()
        rd.Done()

        line_reader = reader.StringLineReader(code_str, self.parse_ctx.arena)
        c_parser = self.parse_ctx.MakeOshParser(line_reader)

        # TODO: it would be nice to point to the location of the expression
        # argument
        src = source.Dynamic('parseCommand()', rd.LeftParenToken())
        with alloc.ctx_SourceCode(self.parse_ctx.arena, src):
            try:
                cmd = main_loop.ParseWholeFile(c_parser)
            except error.Parse as e:
                # This prints the location
                self.errfmt.PrettyPrintError(e)

                # TODO: add inner location info to this structured error
                raise error.Structured(3, "Syntax error in parseCommand()",
                                       rd.LeftParenToken())

        return value.Command(cmd)


class ParseExpr(vm._Callable):

    def __init__(self, parse_ctx, errfmt):
        # type: (parse_lib.ParseContext, ui.ErrorFormatter) -> None
        self.parse_ctx = parse_ctx
        self.errfmt = errfmt

    def Call(self, rd):
        # type: (typed_args.Reader) -> value_t
        code_str = rd.PosStr()
        rd.Done()

        return value.Null


class EvalExpr(vm._Callable):

    def __init__(self, expr_ev):
        # type: (expr_eval.ExprEvaluator) -> None
        self.expr_ev = expr_ev

    def Call(self, rd):
        # type: (typed_args.Reader) -> value_t
        lazy = rd.PosExpr()
        rd.Done()

        result = self.expr_ev.EvalExpr(lazy, rd.LeftParenToken())

        return result
