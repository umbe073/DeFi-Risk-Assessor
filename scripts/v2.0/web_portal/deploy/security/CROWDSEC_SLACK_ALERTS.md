# CrowdSec -> Slack Alert Digest

This optional deploy pack sends new CrowdSec alerts to a Slack incoming webhook.

## Files

- `crowdsec_slack_alerts.sh`
- `crowdsec-slack-alerts.service`
- `crowdsec-slack-alerts.timer`

## Install

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/security/crowdsec_slack_alerts.sh /usr/local/sbin/crowdsec_slack_alerts.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/security/crowdsec-slack-alerts.service /etc/systemd/system/crowdsec-slack-alerts.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/security/crowdsec-slack-alerts.timer /etc/systemd/system/crowdsec-slack-alerts.timer

sudo tee /etc/default/crowdsec-slack-alerts >/dev/null <<'EOF'
CROWDSEC_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/REPLACE/THIS/WITH_REAL_WEBHOOK
CROWDSEC_SLACK_MAX_ALERTS_PER_RUN=10
EOF
sudo chmod 600 /etc/default/crowdsec-slack-alerts

sudo systemctl daemon-reload
sudo systemctl enable --now crowdsec-slack-alerts.timer
sudo systemctl start crowdsec-slack-alerts.service
sudo systemctl status --no-pager crowdsec-slack-alerts.service
sudo systemctl list-timers --all | grep crowdsec-slack-alerts
```

## Notes

- Uses `cscli alerts list -o json` and sends only new alerts based on last seen alert ID.
- State file: `/var/lib/crowdsec-slack/last_alert_id`.
- If webhook is missing, script exits gracefully without sending.

