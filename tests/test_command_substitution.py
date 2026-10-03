"""场景四：命令替换。

应命中：
- 双引号内多层替换：rm-rf 2 次、dd-out 1 次
- 引用的右括号不截断解析：rm-rf 1 次
- 单引号中的替换外观：0 次
- 嵌套达到 32 层上限：rm-rf 1 次；超过上限报错
"""
import pytest

from conftest import hits_by_rule
from dangerous_commands import check_text


def test_nested_subst_in_double_quotes(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf"), "dd-out": ("dd", "of=/dev/sda")})
    text = 'echo "$(echo "$(rm -rf /a)"; dd of=/dev/sda)"; rm -rf /b'
    assert hits_by_rule(text, rules) == {"rm-rf": 2, "dd-out": 1}


def test_quoted_close_paren_does_not_truncate(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    # 替换体内的 ')' 在单引号中，不能提前结束替换
    assert hits_by_rule("echo $(echo ')' ; rm -rf /x)", rules) == {"rm-rf": 1}
    # 双引号同理
    assert hits_by_rule('echo $(echo ")" ; rm -rf /y)', rules) == {"rm-rf": 1}


def test_single_quoted_subst_is_literal(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    assert hits_by_rule("echo '$(rm -rf /x)'", rules) == {}
    assert hits_by_rule("echo '$(echo $(rm -rf /x))'", rules) == {}


def test_subst_in_assignment_and_redir_target(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    text = "A=$(rm -rf /a) echo ok > $(rm -rf /b)"
    assert hits_by_rule(text, rules) == {"rm-rf": 2}


def _nested(depth):
    return "echo $(" * depth + "rm -rf /deep" + ")" * depth


def test_nesting_at_limit(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    assert hits_by_rule(_nested(32), rules) == {"rm-rf": 1}


def test_nesting_beyond_limit_raises(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    with pytest.raises(ValueError):
        check_text(_nested(33), rules)


def test_close_paren_in_subst_comment(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    # 替换体注释中的右括号不能提前结束替换
    assert hits_by_rule("echo $(rm -rf /x # )\n)", rules) == {"rm-rf": 1}
