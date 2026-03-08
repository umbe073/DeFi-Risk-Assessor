# Public Docs Redaction + Publish

Use this flow to publish documentation safely (without leaking internal paths/secrets).

## 1) Build sanitized docs locally (Zensical)

```bash
cd /Users/amlfreak/Desktop/venv
python3 docs/tools/build_public_docs.py
./bin/zensical build -f mkdocs.public.yml
```

## 2) Upload docs to server

```bash
rsync -avz --delete /Users/amlfreak/Desktop/venv/site_public/ linuxuser@YOUR_SERVER_IP:~/site_public/
```

## 3) Server-side publish path

```bash
ssh linuxuser@YOUR_SERVER_IP
sudo mkdir -p /var/www/hodler-suite-docs
sudo rsync -a --delete ~/site_public/ /var/www/hodler-suite-docs/
```

## 4) Nginx docs virtual host (example)

```nginx
server {
    listen 443 ssl http2;
    server_name docs.hodler-suite.com;

    ssl_certificate     /etc/letsencrypt/live/app.hodler-suite.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.hodler-suite.com/privkey.pem;

    root /var/www/hodler-suite-docs;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## 5) Bind website Docs page to public docs URL

Set in `web_portal.env`:

```env
PUBLIC_DOCS_URL=https://docs.hodler-suite.com
```

Then restart:

```bash
sudo systemctl restart hodler-web-portal.service
```
