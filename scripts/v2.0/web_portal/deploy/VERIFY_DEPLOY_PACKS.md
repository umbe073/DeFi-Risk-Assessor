# Deploy Pack Verification Runbook

Use this after deploying the web portal to staging/production to verify the shipped service/timer packs:

- `script-api-watchdog`
- `risk-worker`
- `status-sampler`
- `support-resend-sync`
- `cloudflare-ufw-sync`
- `crowdsec-slack-alerts`
- `uptimerobot-slack-relay`
- `user-telemetry-retention`

## 1) Install verification helper

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/verify_deploy_packs.sh /usr/local/sbin/hodler_verify_deploy_packs.sh
```

## 2) Run baseline verification

```bash
sudo /usr/local/sbin/hodler_verify_deploy_packs.sh --strict --journal-lines 20
```

Optional (run each service once before reading health):

```bash
sudo /usr/local/sbin/hodler_verify_deploy_packs.sh --strict --run-services --journal-lines 40
```

Expected:

- no `FAIL` rows,
- no `WARN` rows in strict mode,
- each timer is `enabled` and `active`,
- each service has `Result=success`.

## 3) Record verification evidence

Save command output as deployment evidence:

```bash
sudo install -d -m 0755 /var/log/hodler-suite
sudo /usr/local/sbin/hodler_verify_deploy_packs.sh --strict --run-services --journal-lines 40 \
  | tee "/var/log/hodler-suite/deploy-pack-verification-$(date +%Y%m%d-%H%M%S).log"
```

## 4) Alert-delivery checks (manual)

Run these checks to confirm external notification paths:

1. Trigger CrowdSec relay:
   `sudo systemctl start crowdsec-slack-alerts.service`
2. Trigger UptimeRobot relay:
   `sudo systemctl start uptimerobot-slack-relay.service`
3. Confirm Slack channel receives the expected relay messages.
4. Trigger support fallback sync:
   `sudo systemctl start support-resend-sync.service`
5. Confirm no ingestion errors in logs:
   `sudo journalctl -u support-resend-sync.service --no-pager -n 80`
6. Trigger status sampler:
   `sudo systemctl start status-sampler.service`
7. Confirm new sample rows are written:
   `sqlite3 /opt/hodler-suite/web_portal/data/status_metrics.db "select count(*) from service_status_samples;"`
8. Trigger telemetry retention one-shot:
   `sudo systemctl start user-telemetry-retention.service`
9. Confirm retention summary appears in logs:
   `sudo journalctl -u user-telemetry-retention.service --no-pager -n 80`
10. Trigger Script API watchdog one-shot:
   `sudo systemctl start script-api-watchdog.service`
11. Confirm watchdog log is healthy:
   `sudo journalctl -u script-api-watchdog.service --no-pager -n 80`
12. Trigger risk worker one-shot:
   `sudo systemctl start risk-worker.service`
13. Confirm risk worker reports idle/processed and no hard errors:
   `sudo journalctl -u risk-worker.service --no-pager -n 80`

## 5) Failure triage

1. Missing units:
   - reinstall unit files from deploy pack docs,
   - run `sudo systemctl daemon-reload`,
   - re-enable timer (`sudo systemctl enable --now <timer>`).
2. Timer not active:
   - inspect timer unit syntax (`systemctl cat <timer>`),
   - check server clock and timezone (`timedatectl status`).
3. Service result not successful:
   - inspect logs with `journalctl -u <service> -n 120 --no-pager`,
   - verify env files/secrets expected by the corresponding script.
