# Deployment

This MCP server is deployed to the Pathfinder DO droplet as a Docker container.

## Quick Reference

| Field | Value |
|---|---|
| Droplet | `root@170.64.197.158` |
| Service name | `meta-ads` |
| URL | `https://meta-ads.mcp.pathfindermarketing.com.au/mcp` |
| Docker image | `australia-southeast1-docker.pkg.dev/pathfinder-383411/cloud-run-source-deploy/meta-ads-mcp:latest` |
| Env file | `/opt/pmin-mcpinfrastructure/env/meta-ads.env` |
| Full docs | [PM-Labs/pmin-mcpinfrastructure](https://github.com/PM-Labs/pmin-mcpinfrastructure) -> `docs/runbooks/meta-ads.md` |

## Deploy

```bash
gcloud builds submit --tag australia-southeast1-docker.pkg.dev/pathfinder-383411/cloud-run-source-deploy/meta-ads-mcp --project pathfinder-383411
ssh root@170.64.197.158 "cd /opt/pmin-mcpinfrastructure && docker compose pull meta-ads && docker compose up -d meta-ads"
```

## Rollback

```bash
ssh root@170.64.197.158 "cd /opt/pmin-mcpinfrastructure && docker compose stop meta-ads"
# Revert to previous image tag, then: docker compose up -d meta-ads
```

## Operational Docs

See [PM-Labs/pmin-mcpinfrastructure](https://github.com/PM-Labs/pmin-mcpinfrastructure) for:
- Architecture: `docs/ARCHITECTURE.md`
- Runbook: `docs/runbooks/meta-ads.md`
- Cron jobs: `docs/CRON-JOBS.md`
