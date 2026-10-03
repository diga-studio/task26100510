"""Shell 子集解析：把会话文本拆成简单命令序列。

支持的子集：简单命令、前置赋值、重定向（< > >>）、可嵌套命令替换 $(...)，
以及用分号、换行、&&、||、| 连接的命令。解析全程不执行输入文本。
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_SUBSTITUTION_DEPTH = 32

_BLANKS = " \t"
# 未引用时结束一个词元的字符（')' 用于结束命令替换体）。
_WORD_END = set(" \t\n;&|<>)")


class ParseError(ValueError):
    """输入文本不符合约定的 Shell 子集。"""


@dataclass(frozen=True)
class Word:
    """一个词元。

    value:  去除引号、拼接相邻片段后的字面值。
    opaque: 是否包含命令替换（含替换的词元不等于任何字面规则词元）。
    quoted: 与 value 等长，标记每个字符是否来自引用或转义（用于赋值判定）。
    """

    value: str
    opaque: bool = False
    quoted: tuple[bool, ...] = ()


@dataclass(frozen=True)
class Command:
    """一个简单命令：按顺序排列的词元（重定向及目标已剔除）。"""

    words: tuple[Word, ...]


def parse_commands(text: str, max_depth: int = MAX_SUBSTITUTION_DEPTH) -> list[Command]:
    """把文本解析为简单命令列表，命令替换体递归解析并追加到同一列表。"""
    parser = _Parser(text, max_depth)
    parser.parse_list(stop_at_paren=False, depth=0)
    return parser.commands


class _Parser:
    def __init__(self, text: str, max_depth: int) -> None:
        self.text = text
        self.n = len(text)
        self.pos = 0
        self.max_depth = max_depth
        self.commands: list[Command] = []

    def error(self, msg: str) -> None:
        raise ParseError(f"{msg}（偏移 {self.pos}）")

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < self.n else ""

    def skip_blanks(self) -> None:
        """跳过空白与反斜线换行（行连接整体消失）。"""
        while self.pos < self.n:
            c = self.text[self.pos]
            if c in _BLANKS:
                self.pos += 1
            elif c == "\\" and self.pos + 1 < self.n and self.text[self.pos + 1] == "\n":
                self.pos += 2
            else:
                break

    def skip_comment(self) -> None:
        while self.pos < self.n and self.text[self.pos] != "\n":
            self.pos += 1

    def parse_list(self, stop_at_paren: bool, depth: int) -> None:
        """解析命令序列，直到文本结束或（在替换体内）遇到右括号。"""
        while True:
            self.skip_blanks()
            c = self.peek()
            if c == "":
                if stop_at_paren:
                    self.error("命令替换缺少右括号")
                return
            if c == ")":
                if stop_at_paren:
                    return
                self.error("多余的右括号")
            if c == "#":
                self.skip_comment()
                continue
            if c in ";\n":
                self.pos += 1
                continue
            if c == "&":
                if self.text[self.pos : self.pos + 2] == "&&":
                    self.pos += 2
                    continue
                self.error("不支持的 & 用法")
            if c == "|":
                if self.text[self.pos : self.pos + 2] == "||":
                    self.pos += 2
                else:
                    self.pos += 1
                continue
            self.parse_simple_command(depth)

    def parse_simple_command(self, depth: int) -> None:
        words: list[Word] = []
        while True:
            self.skip_blanks()
            c = self.peek()
            if c == "" or c == ")" or c in ";\n&|":
                break
            if c == "#":
                self.skip_comment()
                continue
            if c in "<>":
                self.parse_redirect(depth)
                continue
            word, ended_by_redirect = self.read_word(depth)
            if (
                ended_by_redirect
                and not word.opaque
                and word.value.isdigit()
                and not any(word.quoted)
            ):
                # 紧贴操作符且未引用的纯数字是文件描述符，不是普通词元。
                self.parse_redirect(depth)
                continue
            words.append(word)
        if words:
            self.commands.append(Command(tuple(words)))

    def parse_redirect(self, depth: int) -> None:
        """消费重定向操作符及其后一个目标词元，二者均不进入命令词元。"""
        if self.peek() == ">":
            self.pos += 1
            if self.peek() == ">":
                self.pos += 1
        else:  # '<'
            self.pos += 1
        self.skip_blanks()
        if self.peek() == "" or self.peek() in ";\n&|<>)" :
            self.error("重定向缺少目标")
        self.read_word(depth)  # 目标词元（其中可能含命令替换，需照常解析）

    def read_word(self, depth: int) -> tuple[Word, bool]:
        """读取一个词元，返回 (词元, 是否因未引用的重定向符而结束)。"""
        chars: list[str] = []
        quoted: list[bool] = []
        opaque = False
        ended_by_redirect = False
        while self.pos < self.n:
            c = self.text[self.pos]
            if c in _WORD_END:
                if c in "<>":
                    ended_by_redirect = True
                break
            if c == "\\":
                nxt = self.text[self.pos + 1] if self.pos + 1 < self.n else ""
                if nxt == "\n":
                    self.pos += 2
                    continue
                if nxt == "":
                    self.error("反斜线后缺少字符")
                chars.append(nxt)
                quoted.append(True)
                self.pos += 2
                continue
            if c == "'":
                self.pos += 1
                self.read_single_quoted(chars, quoted)
                continue
            if c == '"':
                self.pos += 1
                if self.read_double_quoted(chars, quoted, depth):
                    opaque = True
                continue
            if c == "$" and self.pos + 1 < self.n and self.text[self.pos + 1] == "(":
                opaque = True
                self.pos += 2
                self.parse_substitution_body(depth)
                continue
            chars.append(c)
            quoted.append(False)
            self.pos += 1
        return Word("".join(chars), opaque, tuple(quoted)), ended_by_redirect

    def read_single_quoted(self, chars: list[str], quoted: list[bool]) -> None:
        """单引号内全部按字面处理，不识别命令替换。"""
        while True:
            if self.pos >= self.n:
                self.error("单引号未闭合")
            c = self.text[self.pos]
            if c == "'":
                self.pos += 1
                return
            chars.append(c)
            quoted.append(True)
            self.pos += 1

    def read_double_quoted(self, chars: list[str], quoted: list[bool], depth: int) -> bool:
        """双引号：反斜线仅对 $、"、\\ 和换行生效；命令替换仍生效。"""
        had_substitution = False
        while True:
            if self.pos >= self.n:
                self.error("双引号未闭合")
            c = self.text[self.pos]
            if c == '"':
                self.pos += 1
                return had_substitution
            if c == "\\":
                nxt = self.text[self.pos + 1] if self.pos + 1 < self.n else ""
                if nxt in '$"\\':
                    chars.append(nxt)
                    quoted.append(True)
                    self.pos += 2
                    continue
                if nxt == "\n":
                    self.pos += 2
                    continue
                chars.append("\\")
                quoted.append(True)
                self.pos += 1
                continue
            if c == "$" and self.pos + 1 < self.n and self.text[self.pos + 1] == "(":
                had_substitution = True
                self.pos += 2
                self.parse_substitution_body(depth)
                continue
            chars.append(c)
            quoted.append(True)
            self.pos += 1

    def parse_substitution_body(self, depth: int) -> None:
        """解析 $( 之后的替换体，直到与之匹配的右括号。"""
        if depth + 1 > self.max_depth:
            self.error(f"命令替换嵌套超过 {self.max_depth} 层")
        self.parse_list(stop_at_paren=True, depth=depth + 1)
        self.pos += 1  # 消费匹配的右括号
