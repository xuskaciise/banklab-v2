# Deploying BankLab V2 to the VPS

The VPS is **shared** with other projects (including BankLab V1). Only touch
BankLab V2's own compose project (`banklab2`), its own directory, and its own
nginx server block. Never run `docker compose down -v`, `docker system prune`,
or restart the shared nginx without the owner's OK.

## Topology (checked on the VPS, 2026-11-13)

```
Browser ──HTTPS──> Cloudflare (proxied; SSL mode "Full (strict)")
                      │ HTTPS
                      ▼
          host nginx 1.24 on the VPS (:80/:443, conf.d/*.conf, certbot certs)
             ├─ bank2.siulabs.so /api/ /admin/ /static/ ─> 127.0.0.1:8100  banklab2 backend (gunicorn + Django + WhiteNoise)
             └─ bank2.siulabs.so everything else        ─> 127.0.0.1:3100  banklab2 frontend (Next.js standalone)
                                                           banklab2 db (Postgres 16, compose-internal network only)
```

The VPS is a 4 vCPU / 16 GB box. Other sites run on the same nginx,
each in its own `conf.d/<site>.conf` with a Let's Encrypt cert:
`bank.siulabs.so` (V1, compose project `banklab`, port 8085; `siulabs.so` redirects there), `estate.`,
`hotel.`, `sams.`, `warehouse.`, `s3.`. Ports already used on 127.0.0.1:
3000, 3009, 3010, 3011, 5433, 8085, 9000–9001. V2 uses **8100** and **3100**.

Cloudflare sits in front because some networks block the VPS IP directly.
Because of that:

- **Visitor IP:** `conf.d/00-cloudflare-realip.conf` already restores it
  from `CF-Connecting-IP` for all sites. Our block sends it as `X-Real-IP`
  plus the `X-BankLab-Proxy` shared secret. Django trusts it only with that
  secret (`CLIENT_IP_HEADER=HTTP_X_REAL_IP`, `PROXY_SHARED_SECRET`). The login
  throttle and audit log rely on it.
- **TLS:** nginx terminates TLS (certbot) and forwards
  `X-Forwarded-Proto: $scheme`, so Django sets `Secure` cookies.
  `DJANGO_SSL_REDIRECT=false`, because nginx/Cloudflare do the redirect.
- **Limits:** Cloudflare drops requests after 100 s and bodies over 100 MB.
  Gunicorn times out at 60 s, and the API caps uploads at 5 MB.

## First deploy (run as root on the VPS)

1. **DNS:** done. `bank2.siulabs.so` is an `A` record to the VPS IP, proxied.
2. **Code:** the repo is public, so clone it over HTTPS:
   ```bash
   git clone https://github.com/xuskaciise/banklab-v2.git ~/banklab-v2 && cd ~/banklab-v2
   ```
3. **Secrets:**
   ```bash
   cp .env.prod.example .env.prod && chmod 600 .env.prod
   ```
   Fill in `.env.prod` on the server. Generate `POSTGRES_PASSWORD`,
   `DJANGO_SECRET_KEY` and `PROXY_SHARED_SECRET` with
   `openssl rand -hex 32`. Never copy them from dev, and never paste them in chat.
4. **Build and start:**
   ```bash
   ./deploy/deploy.sh
   ```
   This builds the images, starts db/backend/frontend, runs `migrate`, and
   waits for the backend to report healthy.
5. **nginx site.** These commands add only our file, then test before reloading.
   Use reload, not restart:
   ```bash
   cp deploy/nginx-banklab2.conf /etc/nginx/conf.d/banklab2.conf
   sed -i "s/PROXY_SHARED_SECRET/$(grep ^PROXY_SHARED_SECRET= .env.prod | cut -d= -f2)/" /etc/nginx/conf.d/banklab2.conf
   chmod 600 /etc/nginx/conf.d/banklab2.conf
   nginx -t && systemctl reload nginx
   ```
6. **TLS certificate.** Certbot adds the 443 block to our file only:
   ```bash
   certbot --nginx -d bank2.siulabs.so
   ```
7. **Admin user.** The password is typed at the prompt, so it never lands in shell history:
   ```bash
   docker compose -p banklab2 -f docker-compose.prod.yml --env-file .env.prod exec backend \
     python manage.py create_admin --username admin --full-name "..." --phone "..."
   ```
8. **Smoke test:**
   - Open `https://bank2.siulabs.so/api/health`. It should return 200.
   - Log in as the admin.
   - Check that the audit log shows your real IP.
   - Check that the cookies are `Secure`.
   - Check that V1 (`https://bank.siulabs.so`) still works.

## Update

```bash
cd ~/banklab-v2 && git pull && ./deploy/deploy.sh
```

**Rollback:** run `git checkout <previous-tag> && ./deploy/deploy.sh`. deploy.sh takes a DB backup first.
Migrations are forward-only, so take a backup (below) before each update that
adds migrations.

## Backups

The database and uploaded KYC files are the only state.

```bash
# DB (daily via cron, keep 14 days)
docker compose -p banklab2 -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > ~/backups/banklab2-$(date +%F).dump
# Media (KYC photos/signatures)
docker run --rm -v banklab2_media_data:/m -v ~/backups:/b alpine \
  tar czf /b/banklab2-media-$(date +%F).tgz -C /m .
```

**Restore:** run `pg_restore --clean --if-exists -d "$POSTGRES_DB"` inside the
db container, after stopping `backend`.

## Load test before opening to a class

See `docs/design/loadtest.md`. Never run the load test against the
production database. Use a throwaway stack or DB.

## Automatic deploy (GitHub Actions)

- `.github/workflows/ci.yml` runs on every PR and every push to `main`:
  ruff, a migrations check, pytest (Postgres service), typecheck, lint and build.
- `.github/workflows/deploy.yml` runs **after CI passes on `main`** (or by hand
  from the Actions tab). It SSHes to the VPS, checks out the exact commit, and
  runs `deploy/deploy.sh`. That script backs up the DB, runs
  `compose up -d --build`, waits for the backend to become healthy, then
  prunes old images. It touches only the `banklab2` project.

One-time setup (the repo owner does this; never paste keys into chat):

1. **Deploy key on the VPS:** done (`banklab2_deploy`, for root).
2. **Pinned host key.** Run this and copy the output:
   ```bash
   ssh-keyscan -t ed25519 <VPS IP>
   ```
   Check the fingerprint against the server's
   `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`.
3. **GitHub → Settings → Environments → New `production`:**
   - **Required reviewers:** add yourself, so every deploy waits for your click.
   - **Secrets:**
     - `VPS_HOST`: the VPS IP, not the Cloudflare domain, because SSH does not go through Cloudflare.
     - `VPS_USER`
     - `VPS_SSH_KEY`: the private key file contents.
     - `VPS_KNOWN_HOSTS`: the ssh-keyscan line.
   - **Variables (optional):**
     - `APP_DIR`: default `~/banklab-v2`.
     - `BANKLAB_URL`: shown on the run page.
4. **First deploy:** do steps 1–8 of "First deploy" above by hand. After
   that, merging a PR into `main` deploys automatically.

**Rollback:** run the Deploy workflow by hand from an older commit (Actions →
Deploy → Run workflow → pick the tag or branch), or `git checkout <sha> &&
./deploy/deploy.sh` on the server. Restore the DB from `~/backups` only if a
migration must be undone.
