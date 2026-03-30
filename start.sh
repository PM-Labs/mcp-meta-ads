#!/bin/bash
set -e
echo "Starting Meta Ads MCP (Python) on port ${BACKEND_PORT:-8081}..."
python -m meta_ads_mcp --transport streamable-http --host 0.0.0.0 --port "${BACKEND_PORT:-8081}" &
PYTHON_PID=$!
for i in $(seq 1 30); do
  if curl -sf "http://localhost:${BACKEND_PORT:-8081}/mcp" > /dev/null 2>&1; then
    echo "Python MCP server ready"
    break
  fi
  sleep 1
done
echo "Starting OAuth proxy on port ${PORT:-8080}..."
exec node oauth-proxy.js
