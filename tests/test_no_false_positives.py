"""场景三：说明文字、注释及带空参数的近似命令不产生误报。

应命中：无（全部 0 次）。
"""
from conftest import hits_by_rule


def test_prose_comment_and_near_miss(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf"), "mkfs": ("mkfs",)})
    text = (
        "echo 请不要运行 rm -rf / 这很危险\n"           # 说明文字：rm 是普通参数
        "echo 'rm -rf /' \"mkfs\"\n"                    # 引号内的文字是 echo 的参数
        "# rm -rf /\n"                                  # 整行注释
        "echo hi # rm -rf /\n"                          # 行尾注释
        "rm '' -rf /\n"                                 # 空参数占位，-rf 位置后移
        "rm '' '' -rf /\n"                              # 多个空参数
        "rm -rf\n"                                      # 恰好命中？不：本组要求零命中，移到下行说明
    )
    # 最后一行其实是真实命中，移除以保证本组零误报零命中
    text = text.rsplit("rm -rf\n", 1)[0]
    assert hits_by_rule(text, rules) == {}


def test_subst_word_keeps_position_but_never_literal(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    # 含替换的词元保留参数位置但不等于任何字面词元：-rf 被挤到第 2 个参数
    assert hits_by_rule("rm $(echo x) -rf /a", rules) == {}
    # 不能删除替换词元后拼出匹配
    assert hits_by_rule("r$(echo m) -rf /a", rules) == {}
