# Meta Ads MCP Examples

This directory contains example scripts and usage demonstrations for the Meta Ads MCP server.

## Files

### `http_client.py`
A complete example HTTP client that demonstrates how to interact with the Meta Ads MCP server using the HTTP transport.

**Features:**
- Shows how to authenticate with Pipeboard tokens or Meta access tokens
- Demonstrates all basic MCP operations (initialize, list tools, call tools)
- Includes error handling and response formatting
- Ready-to-use client class for integration

**Usage:**
```bash
# Start the MCP server
python -m meta_ads_mcp --transport streamable-http --port 8080

# Run the example (in another terminal)
cd examples
python http_client.py
```

**Authentication:**
- Set `PIPEBOARD_API_TOKEN` environment variable for Pipeboard auth
- Or pass `meta_access_token` parameter for direct Meta API auth

## Adding New Examples

When adding new example files:
1. Include comprehensive docstrings
2. Add usage instructions in comments
3. Update this README with file descriptions
4. Follow the same authentication patterns as `http_client.py` 