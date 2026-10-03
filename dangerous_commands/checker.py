"""把词法结果组织成命令并匹配规则。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .lexer import Op, Word, lex
from .rules import Rule, RuleSet

_ASSIGN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


@dataclass(frozen=True)
class Hit:
    """一次命中：规则标识 + 命令名在原文中的偏移 + 命令词元。"""

    rule_id: str
    offset: int
    command: tuple[str, ...]


def _iter_commands(items):
    current: list[Word | Op] = []
    for item in items:
        if isinstance(item, Op) and item.kind == "sep":
            if current:
                yield current
                current = []
        else:
            current.append(item)
    if current:
        yield current


def _is_assignment(word: Word) -> bool:
    return _ASSIGN_RE.match(word.unquoted_prefix) is not None


def _command_words(cmd_items: list[Word | Op]) -> list[Word]:
    words: list[Word] = []
    skip_next = False
    for item in cmd_items:
        if skip_next:
            skip_next = False
            continue
        if isinstance(item, Op):  # 重定向操作符，跳过其后的目标词元
            skip_next = True
            continue
        words.append(item)
    index = 0
    while index < len(words) and _is_assignment(words[index]):
        index += 1
    return words[index:]


def _match(rule: Rule, name_word: Word, args: list[Word]) -> bool:
    if name_word.has_subst:
        return False
    basename = name_word.text.rsplit("/", 1)[-1]
    if basename != rule.tokens[0]:
        return False
    if len(args) < len(rule.tokens) - 1:
        return False
    for token, arg in zip(rule.tokens[1:], args):
        if arg.has_subst or arg.text != token:
            return False
    return True


def _check(text: str, base_offset: int, depth: int, ruleset: RuleSet, hits: list[Hit]) -> None:
    result = lex(text, base_offset, depth)
    for cmd_items in _iter_commands(result.items):
        words = _command_words(cmd_items)
        if not words:
            continue
        name_word, args = words[0], words[1:]
        for rule in ruleset.rules:
            if _match(rule, name_word, args):
                hits.append(
                    Hit(rule.rule_id, name_word.offset, tuple(w.text for w in words))
                )
    for inner, offset in result.subst_texts:
        _check(inner, offset, depth + 1, ruleset, hits)


def check_text(text: str, rules: RuleSet) -> list[Hit]:
    """静态检查一段 SSH 命令文本，返回全部命中。未命中不代表命令安全。"""
    if not isinstance(rules, RuleSet):
        raise TypeError(f"期望 RuleSet，得到 {type(rules).__name__}")
    hits: list[Hit] = []
    _check(text, 0, 0, rules, hits)
    return hits
