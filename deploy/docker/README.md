# Docker deployment profile

Copy `.env.example` to `.env`, replace every secret, then run:

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
