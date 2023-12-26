from typing import Tuple

def IsValidVarName(s: str) -> bool: ...
def ShouldHijack(s: str) -> bool: ...
def LooksLikeInteger(s: str) -> bool: ...
def LooksLikeFloat(s: str) -> bool: ...

def MatchOshToken(lex_mode_enum_id: int, line: str, start_pos: int) -> Tuple[int, int]: ...
def MatchPS1Token(line: str, start_pos: int) -> Tuple[int, int]: ...
def MatchEchoToken(line: str, start_pos: int) -> Tuple[int, int]: ...
def MatchHistoryToken(line: str, start_pos: int) -> Tuple[int, int]: ...
def MatchGlobToken(line: str, start_pos: int) -> Tuple[int, int]: ...
def MatchBraceRangeToken(line: str, start_pos: int) -> Tuple[int, int]: ...
def MatchJ8Token(line: str, start_pos: int) -> Tuple[int, int]: ...
def MatchJ8StrToken(line: str, start_pos: int) -> Tuple[int, int]: ...

def MatchOption(s: str) -> int: ...
