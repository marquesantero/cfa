"""Tests for cfa.notify — webhook notifications."""

from cfa.obs.notify import SlackNotifier, TeamsNotifier


class TestNotifiers:
    def test_slack_notifier_constructs(self):
        n = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        assert n.url == "https://hooks.slack.com/test"

    def test_slack_notify_does_not_crash(self):
        n = SlackNotifier(webhook_url="https://localhost:9999/nonexistent")
        n.notify("block", "test intent", "PII violation", ["F1", "F2"], policy_bundle="v1", intent_id="abc", hash="hash")

    def test_teams_notifier_constructs(self):
        n = TeamsNotifier(webhook_url="https://outlook.office.com/webhook/test")
        assert "outlook" in n.url

    def test_teams_notify_does_not_crash(self):
        n = TeamsNotifier(webhook_url="https://localhost:9999/nonexistent")
        n.notify("replan", "test", "reason", [], policy_bundle="v1")
