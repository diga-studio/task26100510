"""规则管理与命中匹配。

只报告能从文本确定的静态命中；未命中不代表命令安全。
检查过程绝不执行输入文本，也不依赖实际 Shell 或目标主机。
"""

from __future__ import annotations

import re

from .model import Hit, Rule
from .parser import Command, Word, parse_commands

MAX_RULES = 500
MAX_RULE_TOKENS = 8
MAX_TEXT_BYTES = 64 * 1024

_VAR_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _is_assignment(word: Word) -> bool:
    """未引用的 ASCII 变量名紧接未引用的等号才算赋值。"""
    for index, char in enumerate(word.value):
        if char == "=" and not word.quoted[index]:
            prefix = word.value[:index]
            if not prefix or any(word.quoted[:index]):
                return False
            return _VAR_NAME.fullmatch(prefix) is not None
    return False


def _matches(rule: Rule, name_word: Word, args: tuple[Word, ...]) -> bool:
    tokens = rule.tokens
    if name_word.opaque:
        return False
    # 命令名取最后一个斜杠之后的部分，其余词元逐字比较，均区分大小写。
    if name_word.value.rsplit("/", 1)[-1] != tokens[0]:
        return False
    if len(args) < len(tokens) - 1:
        return False
    for word, token in zip(args, tokens[1:]):
        if word.opaque or word.value != token:
            return False
    return True


class Checker:
    """特权会话危险指令检查器，规则与结果均在内存中。"""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self._rules: list[Rule] = []
        if rules is not None:
            self.set_rules(rules)

    def set_rules(self, rules: list[Rule]) -> None:
        """整组替换规则：最多 500 条，每条最多 8 个词元，标识唯一。"""
        rules = list(rules)
        if len(rules) > MAX_RULES:
            raise ValueError(f"规则数量超过 {MAX_RULES} 条")
        seen: set[str] = set()
        for rule in rules:
            if not isinstance(rule, Rule):
                raise TypeError("规则必须是 Rule 实例")
            if rule.rule_id in seen:
                raise ValueError(f"规则标识重复：{rule.rule_id!r}")
            seen.add(rule.rule_id)
            if len(rule.tokens) > MAX_RULE_TOKENS:
                raise ValueError(f"规则 {rule.rule_id!r} 的词元超过 {MAX_RULE_TOKENS} 个")
        self._rules = rules

    @property
    def rules(self) -> tuple[Rule, ...]:
        return tuple(self._rules)

    def check(self, text: str) -> list[Hit]:
        """检查一段完整的 SSH 命令文本，返回全部命中。"""
        if not isinstance(text, str):
            raise TypeError("text 必须是字符串")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError(f"文本长度超过 {MAX_TEXT_BYTES} 字节")
        hits: list[Hit] = []
        for index, command in enumerate(parse_commands(text)):
            hits.extend(self._check_command(index, command))
        return hits

    def _check_command(self, index: int, command: Command) -> list[Hit]:
        words = command.words
        start = 0
        while start < len(words) and _is_assignment(words[start]):
            start += 1
        if start >= len(words):
            return []  # 纯赋值，没有命令
        name_word = words[start]
        args = words[start + 1 :]
        snapshot = tuple(word.value for word in words[start:])
        return [
            Hit(rule_id=rule.rule_id, command_index=index, command=snapshot)
            for rule in self._rules
            if _matches(rule, name_word, args)
        ]
