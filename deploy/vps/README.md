# Sydney VPS deployment

This profile runs the FastAPI API, RQ worker, Redis, and HTTPS proxy on a
long-lived VPS. The Next.js frontend remains on Vercel. Neon PostgreSQL and
Vercel Blob remain managed services.

## 1. Prepare DNS and the server

Create an `A` record such as `api.example.com` pointing to the VPS IPv4
address. On Ubuntu, install Docker and allow only SSH, HTTP, and HTTPS:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git ufw
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

## 3. Start the API and worker

```bash
chmod +x deploy/vps/deploy.sh
./deploy/vps/deploy.sh
```

Caddy obtains and renews the TLS certificate automatically. Redis has no public
port. FastAPI is reachable only through Caddy on ports 80 and 443.

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
