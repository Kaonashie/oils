#!/usr/bin/env python2
"""
qsn.py: Quoted String Notation.  See doc/qsn.md.

- Slogan: "QSN Adapts Rust's String Literal Notation Express What JSON Can't."
- Rust strings with '' instead of "". Since \' and \" are allowed in Rust, this
  is OK

The QSN encoder needs to decode utf-8 in an error-tolerant fashion, as bash,
mksh, and zsh do for 'printf %q'.  GNU coreutils (ls, stat, cp) also does this
kind of decoding.

help-bash thread:
  Q: Why not make ${var@Q} the same as 'printf %q' output?
  A: It was an accident.

Comments on filename characters:

  .  and  ..  don't have to be quoted
  -  and  _   don't have to be quoted either
              but they are allowed to be
  Empty string isn't a valid filename, but we encode it as '' anyway, for
    readability
  Filenames like '+', 'a+b', ',' and 'a,b' will be quoted, although a given
  implementation could relax this.

TODO:
  - maybe_decode() in addition to decode()

TODO for other implementations:

  - Test suite.  Should it be bash, or Python 3?
  - Python 3 version
  - Pure C version using re2c.  Can this work with NUL bytes in the string?
    - would be nice: if the test suite asserted that every code path is
      covered..
    - then we could use that same test suite on other implementations
  - Would like contributions:
    - DFA-based "push" decoder
    - fun: branchless, SIMD, etc.

  Related code:

  repr() in stringobject.c in Python.  Copied to repr() in oldstl_containers.cc.
  You have to allocate 2 + 4*n bytes.  2 more bytes for the quotes.

Where does Oil Use QSN?

  maybe_shell_encode() is used in several places:

  - to display argv[i]
    - set -x / xtrace
    - 'jobs' list
    - 'getopts' error message
  - to display variable values
    - 'set'
    - declare -p
  - Exposed to the user:
    - printf %q
    - ${var@Q} (not done yet)

  Note that oil still needs string_ops.ShellQuoteB() for backslash shell
  quoting, e.g. for spaces.  Not technically related to QSN.

Oil User API:

  pass s => to_qsn() => var q
  pass q => from_qsn() => var s

  to-qsn $s :q
  from-qsn $q :orig
  test $s = $orig; echo $?

Embedding within JSON strings (?)

  "'\\x00\\''"

Can be shortened to:

  "\\x00\\'"

In other words, we don't need the leading and trailing quotes.  Note that
backslashes are doubled.
"""
from __future__ import print_function

from mycpp.mylib import log
from mycpp import mylib

from typing import List

_ = log

# Note: this used to be in asdl/pretty.py.  But I think it's better to use
# byteiter() here.
"""
# Word characters, - and _, as well as path name characters . and /.
PLAIN_WORD_RE = r'[a-zA-Z0-9\-_./]+'
_PLAIN_WORD_RE = re.compile(PLAIN_WORD_RE + '$')

def IsPlainWord(s):
  # type: (str) -> bool
  if '\n' in s:  # account for the fact that $ matches the newline
    return False
  return bool(_PLAIN_WORD_RE.match(s))
"""

# Show valid UTF-8 where possible, and \x escapes otherwise.  The entire QSN
# string is valid UTF-8, even if the input isn't.  Like other shells, Oil knows
# that '\xce\xce\xbc' is an invalid byte to be escaped, then a UTF-8-encoded
# char.
BIT8_UTF8 = 0

# Show \u escapes where possible, and \x escapes otherwise.  The QSN string is
# valid ASCII, even if the input isn't.  Note: \x escapes are also used for low
# bytes, e.g. \x01 rather than \u{1}.
BIT8_U_ESCAPE = 1

# Show \x escapes no matter.  The QSN string is valid ASCII and NO DECODING is
# attempted.  You may want to use this if LANG != 'utf-8'.
BIT8_X_ESCAPE = 2

MUST_QUOTE = 4  # maybe_shell_encode() uses this, for assoc array keys

# Functions that aren't translated.  We don't define < and > on strings, and it
# can be done more simply with character tests.

if mylib.PYTHON:

    def IsUnprintableLow(ch):
        # type: (str) -> bool
        return ch < ' '

    def IsUnprintableHigh(ch):
        # type: (str) -> bool
        return ch >= '\x7f'  # 0x7f is DEL, 0x7E is ~

    def IsPlainChar(ch):
        # type: (str) -> bool

        # yapf: disable
        return (ch in '.-_/' or
                'a' <= ch and ch <= 'z' or
                'A' <= ch and ch <= 'Z' or
                '0' <= ch and ch <= '9')
        # yapf: enable

    # mycpp can't translate this format string
    def XEscape(ch):
        # type: (str) -> str
        return '\\x%02x' % ord(ch)

    def UEscape(rune):
        # type: (int) -> str
        return r'\u{%x}' % rune


def _encode(s, bit8_display, buf):
    # type: (str, int, mylib.BufWriter) -> bool
    """Helper for maybe_shell_encode(), maybe_encode(), encode()"""
    if bit8_display == BIT8_X_ESCAPE:
        _encode_bytes_x(s, buf)
        return True
    else:
        return EncodeRunes(s, bit8_display, buf)


def maybe_shell_encode(s, flags=0):
    # type: (str, int) -> str
    """Encode strings to a shell-compatible QSN literal.

    Simple strings stay "bare" words for readability, e.g.

    + echo hi
    not

    + 'echo' 'hi'
    """
    # Shell strings sometimes need the $'' prefix, e.g. for $'\x00'.

    # Shell vs. J8
    #   NUL byte: for shell, emit \x00 instead of \0, because if you emit '1'
    #   after, it will be an octal escape \01.  Likewise, emitting 01 or 001
    #   will cause \001 and \0001, both of which are octal escapes.  Neither
    #   QSN or J8 has octal escapes like \0ddd.
    #
    #   QSN understands \u{3bc}, but shell doesn't.  This means that
    #   bit8_display should be BIT8_UTF8, not BIT8_U_ESCAPE.  In that mode, low
    #   bytes are \x01 instead of \u{1}, and high bytes are *literal* UTF-8.
    #
    # If it weren't for \u{3bc}, you could decode J8 in shell with something
    # like:
    #
    # echo -e "${q:1: -1}" | read -d ''
    # echo -e "${q:2: -1}" | read -d ''  # if it starts with $''

    quote = 0  # no quotes

    must_quote = flags & 0b100
    bit8_display = flags & 0b11  # last 2 bits

    if len(s) == 0:  # empty string DOES need quotes!
        quote = 1
    else:
        for ch in s:
            # [a-zA-Z0-9._\-] are filename chars and don't need quotes
            if not must_quote and IsPlainChar(ch):
                continue  # quote is still 0

            #log('quote = 1 %r', ch)
            quote = 1

            if ch in '\\\'\r\n\t\0' or IsUnprintableLow(ch):
                # We know AHEAD of time it needs quotes like $''
                quote = 2  # max quote, so don't look at the rest of the str
                break

    if quote == 0:  # Short circuit
        return s

    # should we also figure out the length?
    parts = []  # type: List[str]

    buf = mylib.BufWriter()
    valid_utf8 = _encode(s, bit8_display, buf)
    parts.append(buf.getvalue())

    if not valid_utf8 or quote == 2:
        prefix = "$'"  # $'' for \xff \u{3bc}, etc.
    else:
        prefix = "'"

    parts.append("'")  # closing quote
    return prefix + ''.join(parts)


def maybe_encode(s, bit8_display=BIT8_UTF8):
    # type: (str, int) -> str
    """Encode simple strings to a "bare" word, and complex ones to a QSN
    literal.

    Used for: ASDL pretty printing.  There, we don't care about the
    validity of shell strings.
    """
    quote = 0

    if len(s) == 0:
        quote = 1
    else:
        for ch in s:
            # [a-zA-Z0-9._-\_] are filename chars and don't need quotes
            if IsPlainChar(ch):
                continue  # quote is still 0

            quote = 1

    if not quote:
        return s

    parts = []  # type: List[str]
    parts.append("'")
    buf = mylib.BufWriter()
    _encode(s, bit8_display, buf)
    parts.append(buf.getvalue())
    parts.append("'")
    return ''.join(parts)


def encode(s, bit8_display=BIT8_UTF8):
    # type: (str, int) -> str
    parts = []  # type: List[str]
    parts.append("'")

    buf = mylib.BufWriter()
    _encode(s, bit8_display, buf)
    parts.append(buf.getvalue())

    parts.append("'")
    return ''.join(parts)


#
# The Real Work
#


def _encode_bytes_x(s, buf):
    # type: (str, mylib.BufWriter) -> None
    """Simple encoder that doesn't do utf-8 decoding.

    For BIT8_X_ESCAPE.
    """

    # TODO: mylib.BufWriter() instead of List[str] produces less GC pressure

    for byte in s:
        #log('byte %r', byte)
        # append to buffer
        if byte == '\\':
            part = r'\\'
        elif byte == "'":
            part = "\\'"
        elif byte == '\n':
            part = '\\n'
        elif byte == '\r':
            part = '\\r'
        elif byte == '\t':
            part = '\\t'
        elif byte == '\0':
            # never generate \0 - JSON and J8 don't have it
            part = '\\x00'

        elif IsUnprintableLow(byte):
            # BIT8_UTF8 is used for shell, so print it with \x.
            part = XEscape(byte)

        elif IsUnprintableHigh(byte):
            part = XEscape(byte)  # no decoding necessary
        else:  # a literal  character
            part = byte

        buf.write(part)


#
# State Machine for QSN Encoding, which needs to decode UTF-8
#

# Input Symbol Types
Ascii = 0  # ASCII byte.  May need escaping later.
Begin2 = 1  # Begin a 2 byte UTF-8 sequence
Begin3 = 2
Begin4 = 3
Cont = 4  # UTF-8 Continuation byte
Invalid = 5  # Invalid UTF-8 byte like 0xff

# States.  They're numbered so you can do > tests.
Start = 0
B2_1 = 1  # 1 byte pending (don't know if they're valid or invalid)
B3_1 = 2
B4_1 = 3

B3_2 = 4  # 2 bytes pending
B4_2 = 5

B4_3 = 6  # 3 bytes pending

# Registers: r1, r2, r3


def EncodeRunes(s, bit8_display, buf):
    # type: (str, int, mylib.BufWriter) -> bool
    """Decode UTF-8 to Runes and Encode QSN.

    Used for J8 as well.

    Returns:
      bool: if the UTF-8 was valid

    TODO:
    - Output \yff instead of \xff
    - I suppose output legacy \v \b ?  What about \/ ?
    - Handle surrogate range.  Can you decode a JSON string with an unpaired
      surrogate like "\udc00" into Oils?  You can decode it in Python and
      JavaScript.  Gah!
      - J8 behaves differently than JSON.  It will use bytes since \\u{1234} is
        for valid runes.
    - Detect overlong encodings -- there are invalid utf-8!
      - So they should not be represented as \\u{123456}; they should be \xff

    Probably should return a list of UTF-8 decode errors:

    - Invalid start byte
    - Invalid continuation byte
    - Incomplete UTF-8 char
    - Over-long UTF-8 encoding
    - Decodes to invalid code point (surrogate)
      - this changed in 2003; WTF-8 allows it

    See osh/string_ops.py.
    """
    valid_utf8 = True
    state = Start

    # Registers to hold bytes not processed
    r1 = ''
    r2 = ''
    r3 = ''

    for byte in s:

        b = ord(byte)

        # Classify input
        if b < 0x7f:
            typ = Ascii
        elif (b >> 6) == 0b10:
            typ = Cont

        elif (b >> 5) == 0b110:
            typ = Begin2
        elif (b >> 4) == 0b1110:
            typ = Begin3
        elif (b >> 3) == 0b11110:
            typ = Begin4
        else:
            typ = Invalid

        # If we're not on a continuation byte, then pending bytes are invalid.
        if typ != Cont:
            if state >= B2_1:  # at least invalid 1 byte
                valid_utf8 = False
                buf.write(XEscape(r1))
            if state >= B3_2:  # at least 2 invalid bytes
                buf.write(XEscape(r2))
            if state >= B4_3:  # 3 invalid bytes
                buf.write(XEscape(r3))

        if typ == Ascii:
            state = Start

            # append to buffer
            if byte == '\\':
                out = r'\\'
            elif byte == "'":
                out = "\\'"
            elif byte == '\n':
                out = '\\n'
            elif byte == '\r':
                out = '\\r'
            elif byte == '\t':
                out = '\\t'
            elif byte == '\0':
                # Don't output \0 because bytes after can change its meaning
                out = '\\x00'
            elif IsUnprintableLow(byte):
                # Even in utf-8 mode, don't print control chars literally!
                # Also, somehow I think it's more readable to display \x01 than \u{1}.
                # Although it breaks the property that hex escapes mean invalid utf-8.
                if bit8_display == BIT8_U_ESCAPE:
                    out = UEscape(ord(byte))
                else:
                    # BIT8_UTF8 is used for shell, so print it with \x.
                    out = XEscape(byte)
            else:
                out = byte

            #log('byte %r out %r', byte, out)
            buf.write(out)

        elif typ == Begin2:
            state = B2_1
            r1 = byte
        elif typ == Begin3:
            state = B3_1
            r1 = byte
        elif typ == Begin4:
            state = B4_1
            r1 = byte

        elif typ == Invalid:
            state = Start
            buf.write(XEscape(byte))
            valid_utf8 = False

        elif typ == Cont:  # No char started, so no continuation bytes
            if state == Start:
                buf.write(XEscape(byte))
                valid_utf8 = False

            elif state == B2_1:
                if bit8_display == BIT8_UTF8:
                    out = r1 + byte  # concatenate
                else:
                    rune = ord(byte) & 0b00111111  # continuation byte is low
                    rune |= (ord(r1) & 0b00011111) << 6  # high
                    out = UEscape(rune)
                buf.write(out)

                state = Start

            elif state == B3_1:
                r2 = byte
                state = B3_2
            elif state == B3_2:
                if bit8_display == BIT8_UTF8:
                    out = r1 + r2 + byte  # concatenate
                else:
                    rune = ord(byte) & 0b00111111  # continuation byte is low
                    rune |= (ord(r2) & 0b00111111) << 6
                    rune |= (ord(r1) & 0b00001111) << 12
                    out = UEscape(rune)
                buf.write(out)

                state = Start

            elif state == B4_1:
                r2 = byte
                state = B4_2
            elif state == B4_2:
                r3 = byte
                state = B4_3
            elif state == B4_3:
                if bit8_display == BIT8_UTF8:
                    out = r1 + r2 + r3 + byte  # concatenate
                else:
                    rune = ord(byte) & 0b00111111  # continuation byte is low
                    rune |= (ord(r3) & 0b00111111) << 6
                    rune |= (ord(r2) & 0b00111111) << 12
                    rune |= (ord(r1) & 0b00000111) << 18
                    out = UEscape(rune)
                buf.write(out)
                state = Start

            else:
                raise AssertionError(state)
        else:
            raise AssertionError(typ)

    #log('STATE %r p = %d', state, p)

    if state >= B2_1:  # at least invalid 1 byte
        valid_utf8 = False
        buf.write(XEscape(r1))
    if state >= B3_2:  # at least 2 invalid bytes
        buf.write(XEscape(r2))
    if state >= B4_3:  # 3 invalid bytes
        buf.write(XEscape(r3))

    return valid_utf8
