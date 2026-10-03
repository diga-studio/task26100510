"""规则定义与规则集。"""
from __future__ import annotations

from dataclasses import dataclass


MAX_RULES = 500
MAX_RULE_TOKENS = 8


@dataclass(frozen=True)
class Rule:
    """一条危险指令规则：唯一标识 + 非空词元序列。"""

    rule_id: str
    tokens: tuple[str, ...]

    def __init__(self, rule_id: str, tokens) -> None:
        tokens = tuple(tokens)
        if not rule_id:
            raise ValueError("rule_id 不能为空")
        if not tokens:
            raise ValueError(f"规则 {rule_id!r} 的词元序列不能为空")
        if len(tokens) > MAX_RULE_TOKENS:
            raise ValueError(
                f"规则 {rule_id!r} 词元数 {len(tokens)} 超过上限 {MAX_RULE_TOKENS}"
            )
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "tokens", tokens)


class RuleSet:
    """整组规则的内存容器，整体替换式设置。"""

    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def set_rules(self, rules) -> None:
        rules = list(rules)
        if len(rules) > MAX_RULES:
            raise ValueError(f"规则数 {len(rules)} 超过上限 {MAX_RULES}")
        seen: set[str] = set()
        for rule in rules:
            if not isinstance(rule, Rule):
                raise TypeError(f"期望 Rule，得到 {type(rule).__name__}")
            if rule.rule_id in seen:
                raise ValueError(f"规则标识重复: {rule.rule_id!r}")
            seen.add(rule.rule_id)
        self._rules = rules

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)
