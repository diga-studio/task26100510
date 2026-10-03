"""验收测试：三组场景 + 嵌套上限。

每组在 docstring 中明确列出应命中的规则及出现次数。
"""

import pytest

from dangerous_commands import Checker, ParseError, Rule
from dangerous_commands.checker import MAX_RULES, MAX_RULE_TOKENS
from dangerous_commands.parser import MAX_SUBSTITUTION_DEPTH

RULES = [
    Rule("rm-rf", ("rm", "-rf")),
    Rule("rm-rf-root", ("rm", "-rf", "/")),
    Rule("shutdown", ("shutdown",)),
]


def checker(rules=RULES):
    return Checker(rules)


def hit_ids(hits):
    return sorted(h.rule_id for h in hits)


class TestGroup1AssignmentPathQuotingRedirect:
    """赋值、路径命令名、引号拼接与重定向混合后仍准确命中。

    应命中：rm-rf 共 8 次，shutdown 共 2 次，rm-rf-root 共 1 次。
    """

    def test_assignment_before_command_is_skipped(self):
        hits = checker().check("PATH=/bin HOME=/root /bin/rm -rf /tmp/x")
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1

    def test_assignment_with_quoted_and_substitution_value(self):
        hits = checker().check('A="x y" B=$(echo hi) rm -rf /tmp/x')
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1

    def test_assignment_after_command_name_is_plain_argument(self):
        hits = checker().check("rm -rf A=1 /tmp/x")
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1（A=1 是普通参数，不影响）

    def test_path_command_name_uses_basename(self):
        hits = checker().check("/usr/bin/rm -rf /tmp/x && /sbin/shutdown -h now")
        assert hit_ids(hits) == ["rm-rf", "shutdown"]  # rm-rf ×1，shutdown ×1

    def test_quote_concatenation_builds_tokens(self):
        hits = checker().check("r'm' ''\"-rf\" /tmp/x")
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1（引号拼接出 rm 与 -rf）

    def test_redirect_operator_and_target_are_ignored(self):
        hits = checker().check("rm 2>out -rf /tmp/x > log")
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1（紧贴的 2 是文件描述符）

    def test_redirect_anywhere_in_command(self):
        hits = checker().check("> out rm < input -rf /tmp/x >> log")
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1

    def test_mixed_pipeline_and_conditionals(self):
        text = "cat f | grep x && A=1 /bin/rm -rf / || shutdown || echo done"
        hits = checker().check(text)
        # rm-rf ×1，rm-rf-root ×1（目标恰为 /），shutdown ×1
        assert hit_ids(hits) == ["rm-rf", "rm-rf-root", "shutdown"]

    def test_same_command_at_two_positions_reports_twice(self):
        hits = checker().check("rm -rf /a; rm -rf /b")
        assert hit_ids(hits) == ["rm-rf", "rm-rf"]  # rm-rf ×2
        assert hits[0].command_index != hits[1].command_index

    def test_longer_rule_matches_prefix_tokens(self):
        hits = checker().check("rm -rf /")
        assert hit_ids(hits) == ["rm-rf", "rm-rf-root"]  # 各 ×1，命令可有更多参数

    def test_escaped_chars_and_line_continuation(self):
        hits = checker().check("r\\m -r\\\nf /tmp/x")
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1（转义拼接、行连接）


class TestGroup2NoFalsePositives:
    """说明文字、注释及带空参数的近似命令不产生误报。

    应命中：仅最后一条命令 rm-rf ×1，其余全部 0 次。
    """

    def test_dangerous_text_as_plain_argument_is_not_reported(self):
        assert checker().check("echo rm -rf /") == []
        assert checker().check('echo "rm -rf /"') == []
        assert checker().check("echo 说明：请不要执行 rm -rf /") == []

    def test_comment_is_ignored(self):
        assert checker().check("# rm -rf /") == []
        assert checker().check("rm # -rf /") == []
        # 注释中的 rm -rf / 不命中；注释前那次命中 rm-rf 与 rm-rf-root 各 ×1
        assert hit_ids(checker().check("rm -rf / # 再来一次 rm -rf /")) == ["rm-rf", "rm-rf-root"]

    def test_empty_argument_breaks_match(self):
        assert checker().check('rm "" -rf /') == []
        assert checker().check("rm '' -rf /") == []

    def test_split_options_are_not_equivalent(self):
        assert checker().check("rm -r -f /") == []
        assert checker().check("rm -fr /") == []

    def test_substitution_word_is_not_a_literal_token(self):
        # 含命令替换的词元保留参数位，但不等于任何字面词元，也不能删掉再拼。
        assert checker().check("rm $(echo -rf) /tmp/x") == []
        assert checker().check("rm -r$(echo f) /tmp/x") == []

    def test_quoted_assignment_lookalike_is_command_name(self):
        assert checker().check('"A=1" rm -rf /') == []  # 命令名是 A=1，不是 rm
        assert checker().check("A\\=1 rm -rf /") == []  # 转义等号不算赋值

    def test_fd_separated_by_blank_is_plain_word(self):
        assert checker().check("rm 2 >out -rf") == []  # 2 是普通参数

    def test_single_quoted_substitution_lookalike(self):
        assert checker().check("echo '$(rm -rf /)'") == []

    def test_one_real_hit_among_lookalikes(self):
        text = "echo 'rm -rf /'; rm '' -rf /; rm -rf /tmp/real"
        hits = checker().check(text)
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1
        assert hits[0].command == ("rm", "-rf", "/tmp/real")


class TestGroup3NestedSubstitution:
    """双引号内多层替换能找到全部内部命令；引用的右括号不截断解析；
    单引号中的替换外观不被检查。

    应命中：见各用例标注。
    """

    def test_multi_level_substitution_in_double_quotes(self):
        text = 'echo "$(echo "$(rm -rf /a; /sbin/shutdown)")"'
        hits = checker().check(text)
        assert hit_ids(hits) == ["rm-rf", "shutdown"]  # rm-rf ×1，shutdown ×1

    def test_quoted_right_paren_does_not_end_substitution(self):
        text = 'echo "$(echo ")"; rm -rf /tmp/x)"'
        hits = checker().check(text)
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1（")" 在引号内不结束替换）

    def test_substitution_in_assignment_value_and_redirect_target(self):
        text = "A=$(rm -rf /a) echo hi > $(/sbin/shutdown)"
        hits = checker().check(text)
        assert hit_ids(hits) == ["rm-rf", "shutdown"]  # 各 ×1

    def test_all_branches_inside_substitution_are_checked(self):
        text = 'x "$(true && rm -rf /a || rm -rf /b; rm -rf /c | cat)"'
        hits = checker().check(text)
        assert hit_ids(hits) == ["rm-rf", "rm-rf", "rm-rf"]  # rm-rf ×3

    def test_single_quotes_disable_substitution(self):
        text = "echo '$(rm -rf /a)'; echo '$(shutdown)'"
        assert checker().check(text) == []

    def test_single_quotes_inside_double_quoted_substitution(self):
        # 替换体内的单引号同样字面化：外观不检查，其余命令照查。
        text = 'echo "$(echo \'$(rm -rf /a)\'; rm -rf /b)"'
        hits = checker().check(text)
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1（仅 /b 那次）

    def test_max_nesting_depth_is_fully_checked(self):
        depth = MAX_SUBSTITUTION_DEPTH
        text = "$(" * depth + "rm -rf /deep" + ")" * depth
        hits = checker().check(text)
        assert hit_ids(hits) == ["rm-rf"]  # rm-rf ×1（达到 32 层仍完整检查）

    def test_beyond_max_nesting_depth_raises(self):
        depth = MAX_SUBSTITUTION_DEPTH + 1
        text = "$(" * depth + "rm -rf /deep" + ")" * depth
        with pytest.raises(ParseError):
            checker().check(text)


class TestLimits:
    def test_rule_count_limit(self):
        rules = [Rule(f"r{i}", ("rm", "-rf")) for i in range(MAX_RULES)]
        assert len(Checker(rules).rules) == MAX_RULES
        with pytest.raises(ValueError):
            Checker(rules + [Rule("extra", ("rm", "-rf"))])

    def test_rule_token_limit(self):
        Checker([Rule("ok", tuple(f"t{i}" for i in range(MAX_RULE_TOKENS)))])
        with pytest.raises(ValueError):
            Checker([Rule("bad", tuple(f"t{i}" for i in range(MAX_RULE_TOKENS + 1)))])

    def test_duplicate_rule_id_rejected(self):
        with pytest.raises(ValueError):
            Checker([Rule("x", ("rm",)), Rule("x", ("rm",))])

    def test_text_size_limit(self):
        c = checker()
        assert c.check("true\n" * 100) == []
        with pytest.raises(ValueError):
            c.check("x" * (64 * 1024 + 1))

    def test_set_rules_replaces_whole_group(self):
        c = checker()
        c.set_rules([Rule("only", ("shutdown",))])
        assert hit_ids(c.check("rm -rf /; shutdown")) == ["only"]
