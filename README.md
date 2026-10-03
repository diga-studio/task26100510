# dangerous_commands

特权会话危险指令识别库（纯 Python、纯内存、静态分析）。从 SSH 会话文本中
按调用方配置的词元规则报告静态命中；未命中不代表命令安全。检查过程绝不
执行输入文本，也不依赖实际 Shell 或目标主机。

## 用法

```python
from dangerous_commands import Rule, RuleSet, check_text

rules = RuleSet()
rules.set_rules([
    Rule("rm-rf", ["rm", "-rf"]),
    Rule("dd-out", ["dd", "of=/dev/sda"]),
])

hits = check_text("/bin/rm -rf /tmp/x; echo done", rules)
for hit in hits:
    print(hit.rule_id, hit.offset, hit.command)
```

## 匹配语义

- 规则词元与命令起始词元逐个匹配，允许命令有更多参数。
- 命令名取最后一个 `/` 之后的部分，其余词元逐字比较，均区分大小写；
  不推断选项等价（`rm -r -f` 不命中 `rm -rf`）。
- 命令名前的前置赋值、任意位置的重定向（`<` `>` `>>` 及其目标词元、
  紧贴的未引用数字文件描述符）不参与匹配。
- 支持单/双引号、反斜线转义、行注释、`;` 换行 `&&` `||` `|` 连接，
  所有分支都检查，不判断执行条件。
- 支持嵌套 `$(...)`（未引用或双引号内），替换体按同样规则独立检查；
  含替换的外层词元保留参数位置但不等于任何字面词元。
- 同一处命令对同一规则只报告一次，不同位置分别报告。

## 限制

- 最多 500 条规则，每条最多 8 个词元。
- 单次文本最长 64 KiB，命令替换最多嵌套 32 层（超出抛 `ValueError`）。

## 测试

```sh
python3 -m pytest tests/
```
