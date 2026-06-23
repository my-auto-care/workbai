# workbai — Operations Runbook

**Product:** AI vehicle inspection transcription and diagnostics (Workbay AI pun: *workbai*).  
**Orchestrator repo path:** `/home/ari/workbai` on `workbay-orchestrator` (167.71.24.70).  
**Runtime host:** `gaid-digitalocean` (167.99.153.77) — Docker Compose stack.

## Topology

| Layer | Host | Role |
|-------|------|------|
| Git / deploy source | GitHub `my-auto-care/workbai` | Application code |
| Orchestrator | 167.71.24.70 | SSH deploy, Zepto sessions, Temporal steps |
| Runtime | 167.99.153.77 | Production containers (API, workers, DB clients) |

Manifest entry: `orchestrator/config/projects.yaml` → `workbai` (`use_zeptoclaw: true`).

## SSH access (orchestrator → gaid)

From the orchestrator droplet as `ari`:

```bash
ssh -o BatchMode=yes root@167.99.153.77
```

Deploy key and `~/.ssh/config` entries should live on the orchestrator only — not on developer laptops for production deploys.

Verify:

```bash
ssh root@167.99.153.77 'docker ps --format "{{.Names}}\t{{.Status}}"'
```

## Deploy (typical)

On orchestrator after `git pull` in `~/workbai`:

```bash
cd ~/workbai
git status
# follow project-specific deploy script or compose, e.g.:
docker compose pull
docker compose up -d
```

Record the image tag or git SHA in the comms master channel when deploying.

## Rollback

1. Note failing SHA: `cd ~/workbai && git rev-parse HEAD`
2. Checkout last known good: `git checkout <sha>`
3. Redeploy compose: `docker compose up -d`
4. Verify health on gaid (app `/health` or documented endpoint).
5. Post rollback note to Workbay Comms master channel.

## Monitoring

| Check | Command / signal |
|-------|------------------|
| Orchestrator health workflow | Temporal UI → `health-check-loop` workflow |
| gaid SSH | `ssh root@167.99.153.77 echo ok` |
| workbai channel | Workbay Comms app → **workbai** project chat |
| Engine workflow | Temporal → `channel-workbai` / linked engine IDs |

Alerts: failed checks notify `channel-master` via FCM (Phase 0 health layer).

## GitHub deploy key rotation (T0.5)

1. On orchestrator: `ssh-keygen -t ed25519 -f ~/.ssh/workbai_deploy -N ''`
2. Add `~/.ssh/workbai_deploy.pub` to GitHub repo **Deploy keys** (read/write if pushes needed).
3. Update `~/workbai/.git/config`:

   ```ini
   [remote "origin"]
       url = git@github.com:my-auto-care/workbai.git
   ```

4. `GIT_SSH_COMMAND='ssh -i ~/.ssh/workbai_deploy' git pull`
5. Revoke old PAT in GitHub → Settings → Developer settings.

## Secrets

After Infisical migration (T0.4), runtime secrets live in Infisical project `workbai` — not in plaintext `.env` on disk.

## Contacts / escalation

- Primary operator: Chad (Workbay Comms master channel + FCM critical class).
- Orchestrator droplet: `systemctl status orchestrator-worker comms-backend comms-worker`.
