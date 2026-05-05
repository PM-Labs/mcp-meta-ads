# Deployment

This MCP server is deployed to the Pathfinder DO droplet as a Docker container.

## Quick Reference

| Field | Value |
|---|---|
| Droplet | `mcp-server` (SSH alias) |
| Service name | `meta-ads` |
| URL | `https://meta-ads.mcp.pathfindermarketing.com.au/mcp` |
| Docker image | `ghcr.io/pmlabs-org/mcp-meta-ads:latest` |
| Env file | `/opt/pmin-mcpinfrastructure/env/meta-ads.env` |
| Full docs | [PM-Labs/pmin-mcpinfrastructure](https://github.com/PM-Labs/pmin-mcpinfrastructure) -> `docs/runbooks/meta-ads.md` |

## Deploy

```bash
# Deployments are automated via CI — push to main triggers build + deploy.
# Manual deploy (if needed):
ssh mcp-server "cd /opt/pmin-mcpinfrastructure && docker compose pull meta-ads && docker compose up -d --force-recreate meta-ads"
```

## Rollback

```bash
ssh mcp-server "cd /opt/pmin-mcpinfrastructure && docker compose stop meta-ads"
# Revert to previous image tag, then: docker compose up -d meta-ads
```

## Operational Docs

See [PM-Labs/pmin-mcpinfrastructure](https://github.com/PM-Labs/pmin-mcpinfrastructure) for:
- Architecture: `docs/ARCHITECTURE.md`
- Runbook: `docs/runbooks/meta-ads.md`
- Cron jobs: `docs/CRON-JOBS.md`
