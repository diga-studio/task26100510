import pytest

from dangerous_commands import Rule, RuleSet


@pytest.fixture
def make_rules():
    def _make(**rules):
        rs = RuleSet()
        rs.set_rules([Rule(rule_id, tokens) for rule_id, tokens in rules.items()])
        return rs

    return _make


def hits_by_rule(text, ruleset):
    counts = {}
    for hit in __import__("dangerous_commands").check_text(text, ruleset):
        counts[hit.rule_id] = counts.get(hit.rule_id, 0) + 1
    return counts
