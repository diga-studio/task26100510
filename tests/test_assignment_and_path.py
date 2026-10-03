"""场景一：前置赋值与路径命令名仍准确命中。

应命中：
- rm-rf（rm -rf）：4 次（路径命令名、多赋值、赋值值含替换、重定向目标含替换各 1）
- dd-out（dd of=）：1 次（赋值只在命令名前有效，命令后的 of= 是普通参数）
"""
from conftest import hits_by_rule


def test_path_basename_and_leading_assignments(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf"), "dd-out": ("dd", "of=/dev/sda")})
    text = (
        "/usr/bin/rm -rf /tmp/x\n"                      # rm-rf：路径命令名取 basename
        "FOO=1 BAR='a b' /bin/rm -rf /y\n"              # rm-rf：前置赋值不参与匹配
        "OUT=$(echo hi) rm -rf /z\n"                    # rm-rf：赋值值里的替换不影响
        "rm -rf /w > $(echo log)\n"                     # rm-rf：重定向目标里的替换不影响
        "dd of=/dev/sda if=/dev/zero bs=1M\n"           # dd-out：首个参数逐字相等，允许更多参数
    )
    assert hits_by_rule(text, rules) == {"rm-rf": 4, "dd-out": 1}


def test_assignment_like_args_are_not_assignments(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    # 命令名之后的 NAME=value 是普通参数；echo 不是 rm
    assert hits_by_rule("echo FOO=1 rm -rf", rules) == {}
    # 引用过的变量名或等号不算赋值：整体是命令名 "FOO=rm"
    assert hits_by_rule("'FOO'=rm -rf", rules) == {}
    assert hits_by_rule("FOO\\==x rm -rf", rules) == {}
