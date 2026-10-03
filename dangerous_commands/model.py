"""数据模型：规则与命中结果。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """一条危险指令规则。

    rule_id: 调用方提供的唯一标识。
    tokens:  非空词元序列，首个词元与命令名（取最后一个斜杠之后部分）比较，
             其余词元与命令起始参数逐字比较，均区分大小写。
    """

    rule_id: str
    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.rule_id, str) or not self.rule_id:
            raise ValueError("rule_id 必须是非空字符串")
        tokens = tuple(self.tokens)
        if not tokens:
            raise ValueError("tokens 必须是非空词元序列")
        for token in tokens:
            if not isinstance(token, str) or not token:
                raise ValueError("规则词元必须是非空字符串")
        object.__setattr__(self, "tokens", tokens)


@dataclass(frozen=True)
class Hit:
    """一次命中。

    rule_id:       命中的规则标识。
    command_index: 命令在解析结果中的序号（含命令替换内部命令，按发现顺序编号），
                   用于区分不同位置出现的相同命令。
    command:       命中命令的词元快照（已去除赋值与重定向，仅保留参数位）。
    """

    rule_id: str
    command_index: int
    command: tuple[str, ...]
