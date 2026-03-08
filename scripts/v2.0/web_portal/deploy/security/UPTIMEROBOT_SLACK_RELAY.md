# UptimeRobot Free -> Slack Relay

UptimeRobot free plan can still reach Slack by polling the read-only `getMonitors` API and relaying status transitions to a Slack Incoming Webhook.

## Install

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/security/uptimerobot_slack_relay.sh /usr/local/sbin/uptimerobot_slack_relay.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/security/uptimerobot-slack-relay.service /etc/systemd/system/uptimerobot-slack-relay.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/security/uptimerobot-slack-relay.timer /etc/systemd/system/uptimerobot-slack-relay.timer
```

## Configuration

Create `/etc/default/uptimerobot-slack-relay`:

```bash
sudo tee /etc/default/uptimerobot-slack-relay >/dev/null <<'EOF'
UPTIMEROBOT_API_KEY=replace_with_read_only_or_monitor_specific_api_key
UPTIMEROBOT_API_URL=https://api.uptimerobot.com/v2/getMonitors
UPTIMEROBOT_MONITOR_ID=
UPTIMEROBOT_TIMEOUT_SECONDS=20
UPTIMEROBOT_STATE_FILE=/var/lib/hodler-suite/uptimerobot_slack_state.json
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/replace/with/webhook
EOF
```

Notes:
- Leave `UPTIMEROBOT_MONITOR_ID` empty when your API key is already monitor-specific.
- First run seeds baseline statuses and does not send historical spam.

## Enable

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now uptimerobot-slack-relay.timer
sudo systemctl start uptimerobot-slack-relay.service
sudo systemctl status --no-pager uptimerobot-slack-relay.timer
sudo journalctl -u uptimerobot-slack-relay.service --no-pager -n 80
```
