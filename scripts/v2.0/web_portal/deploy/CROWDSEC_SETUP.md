# CrowdSec Setup (Ubuntu 24.04 + Nginx + Cloudflare)

This guide enables CrowdSec detection/blocking for the web portal and enrolls your instance in CrowdSec Console.

## 1) Install CrowdSec Engine + Nginx bouncer

```bash
sudo apt update
curl -s https://install.crowdsec.net | sudo sh
sudo apt update
sudo apt install -y crowdsec crowdsec-nginx-bouncer
```

If your APT candidate is pinned to an old distro package, set package priority for CrowdSec repo and run `sudo apt update` again.

## 2) Enable useful collections (Nginx + SSH)

```bash
sudo cscli collections install crowdsecurity/nginx
sudo cscli collections install crowdsecurity/nginx-proxy-manager || true
sudo cscli collections install crowdsecurity/sshd
sudo systemctl restart crowdsec
```

## 3) Create local API key for Nginx bouncer

```bash
sudo cscli bouncers add nginx-bouncer -o raw
```

Copy the generated key and set it in:

`/etc/crowdsec/bouncers/crowdsec-nginx-bouncer.conf`

```ini
API_URL=http://127.0.0.1:8080/
API_KEY=<PASTE_KEY_HERE>
MODE=stream
FALLBACK_REMEDIATION=ban
```

Then reload Nginx:

```bash
sudo systemctl restart nginx
```

## 4) Verify runtime

```bash
sudo systemctl status --no-pager crowdsec
sudo systemctl status --no-pager nginx
sudo cscli metrics
sudo cscli decisions list
```

## 5) Enroll instance in CrowdSec Console (website side + server side)

1. Open https://app.crowdsec.net and create/login account.
2. In Console, create a new enrollment key for this server.
3. Run on server:

```bash
sudo cscli console enroll --name hodler-suite-prod <ENROLLMENT_KEY>
sudo cscli console status
```

4. Return to Console and approve the pending instance enrollment.

## 6) Cloudflare-friendly production notes

- Keep Cloudflare orange-cloud proxy enabled for `app`, root, `www`.
- Keep your existing Cloudflare WAF skip rules for trusted webhook paths.
- Do not block Cloudflare edge ranges at origin (your UFW Cloudflare sync already restricts origin to CF).
- CrowdSec should parse the real client IP from Nginx logs (`CF-Connecting-IP` via `real_ip` setup in Nginx).

## 7) Optional hardening

- Add CrowdSec firewall bouncer if you want host-level blocking in addition to Nginx remediation:

```bash
sudo apt install -y crowdsec-firewall-bouncer-iptables
sudo systemctl enable --now crowdsec-firewall-bouncer
```

- Add custom allowlists for trusted office/admin IPs:

```bash
sudo cscli decisions add -i <YOUR_ADMIN_IP> -t bypass
```

## References

- CrowdSec Linux install: https://docs.crowdsec.net/u/getting_started/installation/linux/
- CrowdSec Nginx bouncer: https://docs.crowdsec.net/u/bouncers/nginx
- Console enroll: https://docs.crowdsec.net/docs/cscli/cscli_console_enroll/
