"""特权会话危险指令识别库（纯内存、静态分析）。"""
from .checker import Hit, check_text
from .rules import Rule, RuleSet

__all__ = ["Hit", "Rule", "RuleSet", "check_text"]
