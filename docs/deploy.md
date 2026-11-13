# Deploying BankLab V2 to the VPS

The VPS is **shared** with other projects (including BankLab V1). Only touch
BankLab V2's own compose project (`banklab2`), its own directory, and its own
nginx server block. Never run `docker compose down -v`, `docker system prune`,
or restart the shared nginx without the owner's OK.

## Topology

```
Browser ──HTTPS──> Cloudflare (proxied, DNS for siulabs.so)
                      │  HTTP (SSL mode "Flexible") or HTTPS ("Full (strict)")
                      ▼
               shared nginx on the VPS (port 80/443)
                 ├─ /api/, /admin/, /static/ ─> banklab2-api:8000  (gunicorn + Django + WhiteNoise)
                 └─ everything else          ─> banklab2-web:3000  (Next.js standalone)
                                                  banklab2 db (Postgres 16, private network only)
```

We use Cloudflare because some networks block the VPS IP directly, so visitors
only ever talk to Cloudflare. Because of that:

- **Visitor IP:** nginx restores it from `CF-Connecting-IP` (only trusted from
  Cloudflare ranges) and sends it as `X-Real-IP`. Django reads it through
  `CLIENT_IP_HEADER=HTTP_X_REAL_IP`. This is used by the login throttle and
  the audit log. Without it, a whole class would look like one Cloudflare IP.
- **Scheme:** nginx forwards `X-Forwarded-Proto: https` when Cloudflare's
  `CF-Visitor` says https, so Django marks cookies `Secure` correctly.
  Keep `DJANGO_SSL_REDIRECT=false` and let Cloudflare redirect HTTP to HTTPS
  ("Always Use HTTPS"). Otherwise Flexible mode loops.
- **Limits:** Cloudflare drops requests after 100 s and bodies over 100 MB.
  Gunicorn times out at 60 s. Uploads are capped at 5 MB by the API.
- **Recommended upgrade:** switch Cloudflare SSL mode to **Full (strict)**
  with a Cloudflare Origin Certificate on nginx (listen 443). Do this only
  after checking it with every other site on the same zone, because SSL mode
  is per zone unless you use a Configuration Rule for this host only.

## First deploy

1. **DNS.** In Cloudflare, add a proxied (orange) record for the V2 host,
   e.g. a subdomain such as `bank.siulabs.so` → VPS IP. Do not move V1's
   `siulabs.so` record until V2 is accepted.
2. **Code.** On the VPS, run these in a new directory next to the other projects:
   ```bash
   git clone <repo-url> ~/banklab-v2 && cd ~/banklab-v2 && git checkout main
   ```
3. **Secrets.** Run `cp .env.prod.example .env.prod && chmod 600 .env.prod`,
   then fill it in. Generate a new `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`
   on the server, and never copy them from dev.
4. **Proxy network.** Find the shared nginx container's network:
   ```bash
   docker inspect <nginx-container> --format '{{json .NetworkSettings.Networks}}'
   ```
   Put that network's name in `PROXY_NETWORK`. If nginx runs on the host
   instead, use any dummy network (`docker network create banklab2-proxy`) and
   point nginx at `127.0.0.1:8100` / `127.0.0.1:3100`.
5. **Build and start:**
   ```bash
   docker compose -p banklab2 -f docker-compose.prod.yml --env-file .env.prod up -d --build
   docker compose -p banklab2 -f docker-compose.prod.yml ps
   ```
   The backend runs `migrate` on start. Check that it shows `healthy`.
6. **Admin user.** Create the first platform admin interactively, so no
   password ever appears in shell history or logs:
   ```bash
   docker compose -p banklab2 -f docker-compose.prod.yml exec backend python manage.py createsuperuser
   ```
7. **nginx.** Copy `deploy/nginx-banklab2.conf` into the shared nginx's conf
   directory, replace `BANKLAB_DOMAIN` and `PROXY_SHARED_SECRET` (same value as in `.env.prod`; `chmod 600` the file), then run `nginx -t` and **reload**
   (not restart):
   ```bash
   docker exec <nginx-container> nginx -t && docker exec <nginx-container> nginx -s reload
   ```
   If `set_real_ip_from` / `real_ip_header` already exist in the shared
   `http {}` block, remove them from our file first.
8. **Smoke test:**
   - Open `https://<host>/api/health`. It should return 200.
   - Log in as the admin.
   - Check that the audit log shows your real IP, not a Cloudflare IP.
   - Check that the response has a `Set-Cookie ... Secure` flag.

## Update

```bash
cd ~/banklab-v2 && git pull
docker compose -p banklab2 -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker image prune -f --filter "label=com.docker.compose.project=banklab2"
```

**Rollback:** run `git checkout <previous-tag>`, then the same `up -d --build`.
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

1. **Deploy key on the VPS.** On your own machine, run:
   ```bash
   ssh-keygen -t ed25519 -f banklab2_deploy -C banklab2-deploy -N ""
   ```
   Then append `banklab2_deploy.pub` to `~/.ssh/authorized_keys` of the
   deploy user on the VPS. Prefer a user that can run docker and owns
   `~/banklab-v2`.
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
