"""Shell 子集词法分析：把文本切成词元与运算符。

只静态解析，绝不执行输入。命令替换体被记录到 subst_texts 供递归检查，
含替换的词元保留位置但不参与字面比较。
"""
from __future__ import annotations

from dataclasses import dataclass, field


MAX_SUBST_DEPTH = 32

_WHITESPACE = " \t\r"


@dataclass
class Word:
    """一个词元。含命令替换的词元不参与字面比较。"""

    text: str
    offset: int
    has_subst: bool = False
    quoted: bool = False
    # 词元首段的未引用字面部分（遇引用或替换即截断），用于识别赋值
    unquoted_prefix: str = ""


@dataclass
class Op:
    """运算符：分隔符（; 换行 && || |）或重定向（< > >>）。"""

    kind: str  # "sep" 或 "redir"
    symbol: str
    offset: int


@dataclass
class LexResult:
    items: list[Word | Op] = field(default_factory=list)
    # 所有命令替换的 (内部文本, 绝对偏移)，按出现顺序
    subst_texts: list[tuple[str, int]] = field(default_factory=list)


def _find_subst_end(text: str, start: int) -> int:
    """从 $( 之后的位置 start 扫描，返回配对右括号的下标。

    单、双引号内的括号不计；双引号内的 $( 仍嵌套。
    """
    depth = 1
    i = start
    n = len(text)
    word_start = True
    while i < n:
        c = text[i]
        if c == "#" and word_start:
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c in _WHITESPACE + "\n":
            word_start = True
            i += 1
            continue
        if c in ";&|":
            word_start = True
            i += 1
            continue
        word_start = False
        if c == "'":
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif c == '"':
            i = _skip_double_quote(text, i + 1)
        elif c == "\\":
            i += 2
        elif c == "$" and i + 1 < n and text[i + 1] == "(":
            depth += 1
            i += 2
        elif c == "(":
            depth += 1
            i += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
            i += 1
        else:
            i += 1
    raise ValueError("命令替换缺少右括号")


def _skip_double_quote(text: str, start: int) -> int:
    """从双引号内容起点扫描，返回闭引号之后的下标。"""
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif c == '"':
            return i + 1
        elif c == "$" and i + 1 < n and text[i + 1] == "(":
            i = _find_subst_end(text, i + 2) + 1
        else:
            i += 1
    raise ValueError("双引号未闭合")


class _WordBuilder:
    def __init__(self, offset: int) -> None:
        self.offset = offset
        self.parts: list[str] = []
        self.prefix: list[str] = []
        self.prefix_open = True
        self.has_subst = False
        self.quoted = False

    def add_unquoted(self, s: str) -> None:
        self.parts.append(s)
        if self.prefix_open:
            self.prefix.append(s)

    def add_escaped(self, s: str) -> None:
        # 反斜线转义的字符不算"未引用"，终止赋值识别的前缀
        self.parts.append(s)
        self.prefix_open = False

    def add_quoted(self, s: str) -> None:
        self.parts.append(s)
        self.quoted = True
        self.prefix_open = False

    def add_subst(self) -> None:
        self.has_subst = True
        self.prefix_open = False

    def build(self) -> Word:
        return Word(
            text="".join(self.parts),
            offset=self.offset,
            has_subst=self.has_subst,
            quoted=self.quoted,
            unquoted_prefix="".join(self.prefix),
        )


def lex(text: str, base_offset: int = 0, depth: int = 0) -> LexResult:
    if depth > MAX_SUBST_DEPTH:
        raise ValueError(f"命令替换嵌套超过 {MAX_SUBST_DEPTH} 层")
    result = LexResult()
    word: _WordBuilder | None = None
    i = 0
    n = len(text)

    def ensure_word(pos: int) -> _WordBuilder:
        nonlocal word
        if word is None:
            word = _WordBuilder(base_offset + pos)
        return word

    def flush_word() -> None:
        nonlocal word
        if word is not None:
            result.items.append(word.build())
            word = None

    def read_subst(pos: int) -> int:
        """处理 $(...)，返回右括号之后的下标。"""
        end = _find_subst_end(text, pos + 2)
        inner = text[pos + 2 : end]
        result.subst_texts.append((inner, base_offset + pos + 2))
        ensure_word(pos).add_subst()
        return end + 1

    while i < n:
        c = text[i]
        if c in _WHITESPACE or c == "\n":
            flush_word()
            if c == "\n":
                result.items.append(Op("sep", "\n", base_offset + i))
            i += 1
        elif c == "#" and word is None:
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c == "\\":
            w = ensure_word(i)
            if i + 1 < n and text[i + 1] != "\n":
                w.add_escaped(text[i + 1])
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise ValueError("单引号未闭合")
            ensure_word(i).add_quoted(text[i + 1 : j])
            i = j + 1
        elif c == '"':
            w = ensure_word(i)
            w.quoted = True
            w.prefix_open = False
            i += 1
            while True:
                if i >= n:
                    raise ValueError("双引号未闭合")
                c = text[i]
                if c == '"':
                    i += 1
                    break
                if c == "\\" and i + 1 < n and text[i + 1] in '$"\\\n':
                    if text[i + 1] != "\n":
                        w.add_quoted(text[i + 1])
                    i += 2
                elif c == "$" and i + 1 < n and text[i + 1] == "(":
                    i = read_subst(i)
                else:
                    w.add_quoted(c)
                    i += 1
        elif c == "$" and i + 1 < n and text[i + 1] == "(":
            i = read_subst(i)
        elif c in "<>":
            flush_word()
            symbol = c
            if c == ">" and i + 1 < n and text[i + 1] == ">":
                symbol = ">>"
                i += 1
            result.items.append(Op("redir", symbol, base_offset + i))
            i += 1
        elif c in ";&|":
            flush_word()
            symbol = c
            if i + 1 < n and text[i + 1] == c and c in "&|":
                symbol = c + c
                i += 1
            result.items.append(Op("sep", symbol, base_offset + i))
            i += 1
        elif c.isdigit() and word is None:
            j = i
            while j < n and text[j].isdigit():
                j += 1
            if j < n and text[j] in "<>":
                symbol = text[j]
                if text[j] == ">" and j + 1 < n and text[j + 1] == ">":
                    symbol = ">>"
                    j += 1
                result.items.append(Op("redir", symbol, base_offset + j))
                i = j + 1
            else:
                ensure_word(i).add_unquoted(c)
                i += 1
        else:
            ensure_word(i).add_unquoted(c)
            i += 1
    flush_word()
    return result
