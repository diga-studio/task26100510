"""场景二：引号拼接与重定向混合后仍准确命中。

应命中：
- rm-rf（rm -rf）：6 次
- 不命中：fd 与操作符被空白隔开、选项被拆成两个词元的情况
"""
from conftest import hits_by_rule


def test_quote_concat_and_redirection(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    text = (
        "r'm' -rf /a\n"                                 # 命中：单引号拼接命令名
        'r"m" "-rf" /b\n'                               # 命中：双引号拼接
        "rm '' -rf /c\n"                                # 不命中：空引号形成空参数，-rf 是第 2 个参数
        "rm 2>err -rf /d\n"                             # 命中：紧贴的 fd 重定向不参与匹配
        "rm 2>>err -rf /e\n"                            # 命中：>> 同理
        "rm -rf /f 2>err\n"                             # 命中：重定向在末尾
        "rm 2 >err -rf /g\n"                            # 不命中：2 被空白隔开，是普通词元
        "rm -r -f /h\n"                                 # 不命中：不推断选项等价
        "rm '-rf' /i\n"                                 # 命中：引号去除后逐字相等
    )
    assert hits_by_rule(text, rules) == {"rm-rf": 6}
