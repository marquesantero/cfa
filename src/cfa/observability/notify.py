"""
CFA Notifications
=================
Webhook-based notifications for governance decisions.

Sends formatted messages to Slack, Teams, or generic webhooks
when a policy evaluation results in BLOCK or REPLAN.

Usage:
    from cfa.observability.notify import SlackNotifier

    notifier = SlackNotifier(webhook_url="https://hooks.slack.com/...")
    notifier.notify_blocked(intent="...", reason="PII violation", faults=[...])
"""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


class WebhookNotifier:
    """Base notifier for generic webhooks."""

    def __init__(self, webhook_url: str) -> None:
        self.url = webhook_url

    def _send(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        req = Request(self.url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            urlopen(req, timeout=10)
        except Exception:
            pass  # Never crash on notification failure

    def notify(self, decision: str, intent: str, reason: str, faults: list[str], **extra: Any) -> None:
        raise NotImplementedError


class SlackNotifier(WebhookNotifier):
    """Sends CFA governance alerts to Slack."""

    def notify(self, decision: str, intent: str, reason: str, faults: list[str], **extra: Any) -> None:
        emoji = {"block": "🚫", "replan": "🔄", "rollback": "↩️"}.get(decision, "⚠️")
        color = {"block": "#ef4444", "replan": "#eab308", "rollback": "#ef4444"}.get(decision, "#6b7280")

        text = f"*{emoji} CFA Governance — {decision.upper()}*\n"
        text += f"*Intent:* {intent[:150]}\n"
        text += f"*Policy:* {extra.get('policy_bundle', 'unknown')}\n"
        text += f"*Reason:* {reason}\n"
        if faults:
            text += f"*Faults:* {', '.join(faults[:5])}\n"
        text += f"\n*Audit:* {extra.get('intent_id', 'n/a')[:8]} | Hash: {extra.get('hash', 'n/a')[:12]}"

        self._send({
            "attachments": [{"color": color, "text": text, "mrkdwn_in": ["text"]}],
        })


class TeamsNotifier(WebhookNotifier):
    """Sends CFA governance alerts to Microsoft Teams."""

    def notify(self, decision: str, intent: str, reason: str, faults: list[str], **extra: Any) -> None:
        color = {"block": "FF0000", "replan": "FFA500", "rollback": "FF0000"}.get(decision, "808080")
        sections = [
            {"activityTitle": f"CFA Governance — {decision.upper()}", "facts": [
                {"name": "Intent", "value": intent[:200]},
                {"name": "Policy", "value": extra.get("policy_bundle", "unknown")},
                {"name": "Reason", "value": reason},
            ]},
        ]
        if faults:
            sections[0]["facts"].append({"name": "Faults", "value": ", ".join(faults[:5])})
        self._send({
            "@type": "MessageCard", "@context": "http://schema.org/extensions",
            "themeColor": color, "title": f"CFA: {decision.upper()}",
            "sections": sections,
        })
