# Sydney VPS deployment

This profile runs the FastAPI API, RQ worker, Redis, and HTTPS proxy on a
long-lived VPS. The Next.js frontend remains on Vercel. Neon PostgreSQL and
Vercel Blob remain managed services.

## 1. Prepare DNS and the server

Create an `A` record such as `api.example.com` pointing to the VPS IPv4
address. On Ubuntu, install Docker and allow only SSH, HTTP, and HTTPS:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates chrony curl git ufw
sudo systemctl enable --now chrony
chronyc waitsync 10 0.1
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw --force enable
```

Sign out and reconnect after adding the user to the Docker group.

## 2. Configure EquityLens

```bash
git clone https://github.com/Linon419/equitylens.git
cd equitylens
cp deploy/vps/.env.example deploy/vps/.env
chmod 600 deploy/vps/.env
```

Fill every value in `deploy/vps/.env`. Use the existing Neon `DATABASE_URL`,
Vercel Blob token, Google client ID, OpenAI/DeepSeek credentials, and application
secrets. `GUEST_SIGNING_SECRET` must match the value configured in Vercel.

Use `REVERSE_PROXY_MODE=caddy` on a clean server where this Compose project owns
ports 80 and 443. Use `REVERSE_PROXY_MODE=external` when 1Panel, Nginx, or
another host proxy already owns HTTPS. The API binds only to
`127.0.0.1:API_PORT`, with `18000` as the default.

## 3. Start the API and worker

```bash
chmod +x deploy/vps/deploy.sh
./deploy/vps/deploy.sh
```

In `caddy` mode, Caddy obtains and renews the TLS certificate automatically. In
`external` mode, configure the existing host proxy to forward the API domain to
`http://127.0.0.1:18000`. Disable proxy buffering and use long read/send
timeouts for research-chat SSE streams. Redis has no public port.

Example Nginx/OpenResty location:

```nginx
location / {
    proxy_pass http://127.0.0.1:18000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
}
```

Useful operations:

```bash
docker compose --env-file deploy/vps/.env -f deploy/vps/docker-compose.yml ps
docker compose --env-file deploy/vps/.env -f deploy/vps/docker-compose.yml logs -f api worker
docker compose --env-file deploy/vps/.env -f deploy/vps/docker-compose.yml restart api worker
```

## 4. Connect Vercel

Set these Production and Preview values in the Vercel web project:

```dotenv
BACKEND_URL=https://api.example.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id
GUEST_SIGNING_SECRET=replace-with-the-same-vps-value
COOKIE_SECURE=true
```

Redeploy the Vercel frontend. Browser requests remain same-origin through the
Next.js BFF; the BFF calls the VPS over HTTPS.

## 5. Verify

```bash
curl https://api.example.com/api/v1/health/live
curl https://api.example.com/api/v1/health/ready
curl https://equitylens-nu.vercel.app/api/health
```

Open a company page and verify company data, graph refresh, chat streaming, and
Google sign-in. The API and worker containers should remain warm between visits.
