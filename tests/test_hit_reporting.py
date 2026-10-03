"""命中报告语义：同一处命令对同一规则只报一次；不同位置分别报告。"""
from dangerous_commands import check_text


def test_same_position_different_rules(make_rules):
    rules = make_rules(**{"rm-any": ("rm",), "rm-rf": ("rm", "-rf")})
    hits = check_text("rm -rf /x", rules)
    assert sorted(h.rule_id for h in hits) == ["rm-any", "rm-rf"]
    assert all(h.offset == 0 for h in hits)


def test_same_command_different_positions(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    hits = check_text("rm -rf /a; rm -rf /b", rules)
    assert [h.rule_id for h in hits] == ["rm-rf", "rm-rf"]
    assert hits[0].offset != hits[1].offset


def test_hit_carries_command_tokens(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    (hit,) = check_text("/bin/rm -rf /tmp/x", rules)
    assert hit.command == ("/bin/rm", "-rf", "/tmp/x")


def test_empty_and_separator_only_text(make_rules):
    rules = make_rules(**{"rm-rf": ("rm", "-rf")})
    assert check_text("", rules) == []
    assert check_text(" ; && \n || | ", rules) == []
    assert check_text("# 只有注释\n", rules) == []
