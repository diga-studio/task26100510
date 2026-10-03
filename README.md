# dangerous-commands

特权会话危险指令识别库。由上层直接调用，规则与检查结果均保存在内存中；
只报告能从文本确定的静态命中，**未命中不代表命令安全**。
检查过程绝不执行输入文本，也不依赖实际 Shell 或目标主机。

## 用法

```python
from dangerous_commands import Checker, Rule

checker = Checker()
checker.set_rules([
    Rule("rm-rf", ("rm", "-rf")),
    Rule("shutdown", ("shutdown",)),
])

hits = checker.check('A=1 /bin/rm -rf /tmp/x; echo "$(rm -rf /y)"')
for hit in hits:
    print(hit.rule_id, hit.command_index, hit.command)
```

- `Rule(rule_id, tokens)`：唯一标识 + 非空词元序列（最多 8 个）。
  首个词元与命令名（取最后一个斜杠之后部分）比较，其余词元与起始参数
  逐字比较，均区分大小写；命令可有更多参数，不推断选项等价。
- `Checker.set_rules(rules)`：整组替换规则（最多 500 条，标识唯一）。
- `Checker.check(text)`：检查一段完整 SSH 命令文本（最长 64 KiB），
  返回全部 `Hit(rule_id, command_index, command)`。同一处命令对同一规则
  只报告一次；不同位置出现相同命令仍分别报告（`command_index` 不同）。

## 支持的 Shell 子集

简单命令、前置赋值、重定向（`<` `>` `>>`）、可嵌套命令替换 `$(...)`（最多
32 层），以及用 `;`、换行、`&&`、`||`、`|` 连接的命令。所有分支都检查，
不判断执行条件；引号内的连接符不是命令边界。词法遵循约定：引号去除与拼接、
反斜线转义、`#` 注释、空引号形成空参数；前置赋值、重定向操作符及目标不参与
匹配；含命令替换的词元保留参数位但不等于任何字面词元。

## 测试

```sh
python3 -m pytest tests/ -q
```
