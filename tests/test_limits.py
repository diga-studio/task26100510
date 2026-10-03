"""非功能边界：500 条规则、64 KiB 文本完整检查。"""
from dangerous_commands import Rule, RuleSet, check_text


def test_500_rules_and_64kib_text():
    rs = RuleSet()
    rs.set_rules([Rule(f"rule-{i}", (f"cmd{i}", "-x")) for i in range(500)])
    filler = "echo harmless\n"
    # 命中命令放在接近 64 KiB 末尾，确认完整检查而非截断
    body = filler * ((64 * 1024 - 20) // len(filler))
    text = body + "cmd499 -x"
    assert len(text) <= 64 * 1024
    hits = check_text(text, rs)
    assert [h.rule_id for h in hits] == ["rule-499"]
