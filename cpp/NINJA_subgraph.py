#!/usr/bin/env python2
"""
cpp/NINJA_subgraph.py
"""

from __future__ import print_function

import os
import sys

from build import ninja_lib
from build.ninja_lib import log


# CPP bindings and some generated code have implicit dependencies on these headers
ASDL_H = [
    '_gen/asdl/hnode.asdl.h',
    '_gen/core/runtime.asdl.h',
    '_gen/frontend/syntax.asdl.h',
    '_gen/frontend/types.asdl.h',

    # synthetic
    '_gen/frontend/id_kind.asdl.h',
    '_gen/frontend/option.asdl.h',
]

GENERATED_H = [
    '_gen/frontend/arg_types.h',
    # NOTE: there is no cpp/arith_parse.h

    '_gen/frontend/consts.h',
    '_gen/core/optview.h',  # header only
]

def NinjaGraph(ru):
  n = ru.n

  n.comment('Generated by %s' % __name__)
  n.newline()

  ru.cc_library(
      '//cpp/leaky_core', 
      srcs = ['cpp/leaky_core.cc'],
      # No implicit deps on ASDL, but some files do
  )

  ru.cc_binary(
      'cpp/leaky_core_test.cc',
      deps = [
        '//cpp/leaky_core',
        '//mycpp/runtime',
        ],
      matrix = ninja_lib.COMPILERS_VARIANTS)

  # TODO: could split these up more, with fine-grained ASDL deps?
  ru.cc_library(
      '//cpp/leaky_bindings', 
      srcs = [
        'cpp/leaky_frontend_flag_spec.cc',
        'cpp/leaky_frontend_match.cc',
        'cpp/leaky_frontend_tdop.cc',
        'cpp/leaky_osh.cc',
        'cpp/leaky_pgen2.cc',
        'cpp/leaky_pylib.cc',
        'cpp/leaky_stdlib.cc',
        'cpp/leaky_libc.cc',
      ],
      implicit = ASDL_H + GENERATED_H,  # TODO: express as proper deps?
  )

  ru.cc_binary(
      'cpp/gc_binding_test.cc',
      deps = [
        '//cpp/leaky_bindings',
        '//mycpp/runtime',
        ],
      matrix = ninja_lib.COMPILERS_VARIANTS)

  ru.cc_binary(
      'cpp/leaky_binding_test.cc',
      deps = [
        '//cpp/leaky_bindings',
        '//cpp/leaky_core',  # could move this
        '//mycpp/runtime',
        ],
      matrix = ninja_lib.COMPILERS_VARIANTS)

  ru.cc_library(
      '//ASDL_CC',  # TODO: split these up?
      srcs = [
        '_gen/core/runtime.asdl.cc',
        '_gen/frontend/syntax.asdl.cc',
        '_gen/frontend/id_kind.asdl.cc',

        # NOT generated due to --no-pretty-print-methods
        # '_gen/frontend/types.asdl.cc',
        # '_gen/asdl/hnode.asdl.cc',
        # '_gen/frontend/option.asdl.cc',
      ],
      implicit = ASDL_H + GENERATED_H,  # TODO: express as proper deps?
  )

  ru.cc_library(
      # TODO: split these up?
      '//GENERATED_CC',
      srcs = [
        '_gen/frontend/consts.cc',
        '_gen/osh/arith_parse.cc',
      ],
      implicit = ASDL_H + GENERATED_H,  # TODO: express as proper deps?
  )

  ru.cc_library(
      '//frontend/arg_types',
      srcs = [ '_gen/frontend/arg_types.cc' ],
      implicit = ASDL_H + GENERATED_H,  # TODO: express as proper deps?
  )

  ru.cc_binary(
      'cpp/leaky_flag_spec_test.cc',

      deps = [
        '//cpp/leaky_bindings',  # TODO: It only needs cpp/leaky_frontend_flag_spec.cc
        '//frontend/arg_types',
        '//mycpp/runtime',
        ],
      matrix = [
        ('cxx', 'dbg', '-D CPP_UNIT_TEST'),
        ('cxx', 'asan', '-D CPP_UNIT_TEST'),
        ('clang', 'coverage', '-D CPP_UNIT_TEST'),
      ]
  )

  # Main program!
  ru.cc_binary(
      '_gen/bin/osh_eval.mycpp.cc',
      implicit = ASDL_H + GENERATED_H,  # TODO: express
      matrix = ninja_lib.COMPILERS_VARIANTS,
      top_level = True,  # _bin/cxx-dbg/osh_eval
      deps = [
        '//cpp/leaky_core',
        '//cpp/leaky_bindings',
        '//frontend/arg_types',
        '//ASDL_CC',
        '//GENERATED_CC',
        '//mycpp/runtime',
        ]
      )

  # TODO: add more variants?
  COMPILERS_VARIANTS = ninja_lib.COMPILERS_VARIANTS + [
      # note: these could be clang too
      ('cxx', 'uftrace'),
      ('cxx', 'tcmalloc'),

      ('cxx', 'dumballoc'),
      ('cxx', 'alloclog'),
  ]
