# Deploying SolarRT on your own VPS

The finished setup:

```
Internet ──443/80──▶ Caddy (automatic HTTPS) ──internal network──▶ SolarRT app (Docker, read-only)
                                                                      └─ volume: feedback.jsonl
```

- **Cost:** a small VPS (1 vCPU, 1–2 GB RAM, Ubuntu 24.04) is plenty. Hetzner, DigitalOcean, Vultr,
  OVH and others cost about €4–6/month.
- **Address:** without a domain, use the free **sslip.io** name for your server's IP. For IP
  `203.0.113.5`, the address is `203-0-113-5.sslip.io`. Caddy still gets a real HTTPS certificate for it.
  You can switch to your own domain at any time (see the end of this guide).

## 1. Create the server

1. At your VPS provider, create an **Ubuntu 24.04** server and add your **SSH key**. If you don't have
   one, run `ssh-keygen -t ed25519` on your PC. The public key is in `%USERPROFILE%\.ssh\id_ed25519.pub`.
2. Note the server's public IPv4 address.

## 2. Secure the server (one time)

Copy the setup script to the server and run it. **Read it first; it changes SSH and firewall settings.**

```bash
scp deploy/setup-server.sh root@203.0.113.5:
ssh root@203.0.113.5
bash setup-server.sh solar "$(cat ~/.ssh/authorized_keys | head -1)"
```

The script creates the user `solar` with your key, disables root and password logins, opens only ports
22/80/443, turns on automatic security updates and fail2ban, and installs Docker. **Before closing the root
session, open a new terminal and check** that `ssh solar@203.0.113.5` works.

## 3. Upload SolarRT

From your PC, in the project folder (`SolarRT2`):

```bash
scp -r solarrt Dockerfile requirements.txt deploy solar@203.0.113.5:~/SolarRT2/
```

If you use a private GitHub repository instead, run `git clone` on the server.

## 4. Configure and start

```bash
ssh solar@203.0.113.5
cd ~/SolarRT2/deploy
cp .env.example .env
nano .env        # set your domain and include 127.0.0.1 in SOLARRT_ALLOWED_HOSTS for container health checks
                 # set SOLARRT_ADMIN_TOKEN to the output of:  openssl rand -hex 32
chmod 600 .env
chmod +x *.sh
docker compose up -d --build
docker compose ps          # both services "running"; app "healthy"
```

Open `https://203-0-113-5.sslip.io`. The first visit can take up to a minute while Caddy gets the certificate.

## 5. Point the Android app at it

```powershell
powershell -ExecutionPolicy Bypass -File mobile\build.ps1 -ApiBase https://203-0-113-5.sslip.io -Release
```

See [ANDROID.md](ANDROID.md) for the signing key, which you need to create once.

**CORS note:** Release Android builds refuse `http://` addresses - must use `https://`. The Caddy reverse proxy internally trusts `*` for `forwarded-allow-ips` since port 8000 is only reachable on the Docker internal network. For custom domains, Caddy auto-gets Let's Encrypt certificates.

If you need to restrict origins, set `SOLARRT_CORS_ORIGINS` in `.env` as a comma-separated list (e.g. `https://solarrt.example.com,https://www.solarrt.example.com`).

For the desktop app to forward its users' feedback to you, set `SOLARRT_FEEDBACK_FORWARD_URL` to
`https://203-0-113-5.sslip.io/api/feedback` before building it.

## Day-to-day

| Task | Command (on the server, in `~/SolarRT2/deploy`) |
|---|---|
| Update after uploading new code | `./update.sh` (backs up feedback, rebuilds, restarts, checks health) |
| Read feedback | `curl -H "Authorization: Bearer $(grep ^SOLARRT_ADMIN_TOKEN= .env \| cut -d= -f2)" https://<domain>/api/feedback` |
| Back up feedback | `./backup.sh` (daily: `crontab -e` → `0 3 * * * $HOME/SolarRT2/deploy/backup.sh`) |
| Logs (errors only, no visitor data) | `docker compose logs --tail 100 app` |
| Restart | `docker compose restart` |
| Status | `docker compose ps` |

Copy backups off the server now and then:
`scp -r solar@203.0.113.5:~/solarrt-backups ./`

## Monitoring (recommended)

Add a free uptime check, such as UptimeRobot or Better Stack, on `https://<domain>/api/health`, so you get an
email if the site goes down.

## Using your own domain later

1. At your domain registrar, add an **A record**: `solarrt.yourdomain.com` → your server's IP.
2. In `.env`, set `SOLARRT_DOMAIN=solarrt.yourdomain.com` and
   `SOLARRT_ALLOWED_HOSTS=solarrt.yourdomain.com`. To keep the old address working, add it after a comma.
3. Run `docker compose up -d`. Caddy gets the new certificate automatically.
4. Rebuild the Android app with the new `-ApiBase`.

## Troubleshooting

- **Certificate not issued:** ports 80/443 must be reachable. Check your provider's cloud firewall as well
  as ufw. Check that `SOLARRT_DOMAIN` matches the IP exactly. Then run `docker compose logs caddy`.
- **"Invalid host header" (400):** add the address you're using to `SOLARRT_ALLOWED_HOSTS`.
- **App unhealthy:** `docker compose logs app`. The most likely cause is the server being unable to reach
  NOAA (outbound internet).
