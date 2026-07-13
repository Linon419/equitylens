# Docker deployment profile

Copy `.env.example` to `.env`, replace every secret, then run:

Authentication requires these profile values:

```dotenv
GOOGLE_CLIENT_ID=replace-with-google-client-id
NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id
FRONTEND_URL=https://equitylens.example.com
BACKEND_URL=http://api:8000
COOKIE_SECURE=true
```

Use `COOKIE_SECURE=false` only for native HTTP development on localhost.

```bash
docker compose config
docker compose build
docker compose up --wait
```

Health endpoints:

- Frontend: `http://localhost:3000/api/health`
- Backend: `http://localhost:8000/api/v1/health/live`

`API_PORT` and `WEB_PORT` can change the host ports when either default port is
already occupied.

Stop the containers started by this profile with:

```bash
docker compose down
```
