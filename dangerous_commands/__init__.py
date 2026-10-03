"""特权会话危险指令识别库：纯内存、静态分析，不执行输入文本。"""

from .checker import Checker
from .model import Hit, Rule
from .parser import ParseError

__all__ = ["Checker", "Hit", "ParseError", "Rule"]
