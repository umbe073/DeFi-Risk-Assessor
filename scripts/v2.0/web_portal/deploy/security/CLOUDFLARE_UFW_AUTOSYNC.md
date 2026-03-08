# Cloudflare UFW Auto-Sync (Monthly)

This deploy pack keeps origin `80/443` UFW allow-lists aligned with Cloudflare IP ranges automatically.

## Files

- `cloudflare_ufw_sync.sh`
- `cloudflare-ufw-sync.service`
- `cloudflare-ufw-sync.timer`

## Install On Server

```bash
sudo install -m 0755 /opt/hodler-suite/web_portal/deploy/security/cloudflare_ufw_sync.sh /usr/local/sbin/cloudflare_ufw_sync.sh
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/security/cloudflare-ufw-sync.service /etc/systemd/system/cloudflare-ufw-sync.service
sudo install -m 0644 /opt/hodler-suite/web_portal/deploy/security/cloudflare-ufw-sync.timer /etc/systemd/system/cloudflare-ufw-sync.timer
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflare-ufw-sync.timer
sudo systemctl start cloudflare-ufw-sync.service
sudo systemctl status --no-pager cloudflare-ufw-sync.service
sudo systemctl list-timers --all | grep cloudflare-ufw-sync
```

## Optional Dry Run

```bash
sudo DRY_RUN=1 /usr/local/sbin/cloudflare_ufw_sync.sh
```

## Notes

- The script only manages rules tagged with comments `cf-auto-v4` and `cf-auto-v6`.
- Existing non-tagged firewall rules are untouched.
- Keep your SSH allow rule separate from this automation.
