# Streamable HTTP Transport Setup

## Overview

Meta Ads MCP supports **Streamable HTTP Transport**, which allows you to run the server as a standalone HTTP API. This enables direct integration with web applications, custom dashboards, and any system that can make HTTP requests.

## Quick Start

### 1. Start the HTTP Server

```bash
# Basic HTTP server (default: localhost:8080)
python -m meta_ads_mcp --transport streamable-http

# Custom host and port
python -m meta_ads_mcp --transport streamable-http --host 0.0.0.0 --port 9000
```

### 2. Set Authentication

Set your Pipeboard token as an environment variable:

```bash
export PIPEBOARD_API_TOKEN=your_pipeboard_token
```

Or alternatively, use a direct Meta access token:

```bash
export META_ACCESS_TOKEN=your_meta_access_token
```

### 3. Make HTTP Requests

The server accepts JSON-RPC 2.0 requests at the `/mcp/` endpoint:

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "X-PIPEBOARD-API-TOKEN: your_pipeboard_token" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {
      "name": "get_ad_accounts",
      "arguments": {"limit": 5}
    }
  }'
```

## Configuration Options

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--transport` | Transport mode | `stdio` |
| `--host` | Server host address | `localhost` |
| `--port` | Server port | `8080` |

### Examples

```bash
# Local development server
python -m meta_ads_mcp --transport streamable-http --host localhost --port 8080

# Production server (accessible externally)
python -m meta_ads_mcp --transport streamable-http --host 0.0.0.0 --port 8080

# Custom port
python -m meta_ads_mcp --transport streamable-http --port 9000
```

## Authentication

### Primary Method: Pipeboard Token (Recommended)

1. Sign up at [Pipeboard.co](https://pipeboard.co)
2. Generate an API token at [pipeboard.co/api-tokens](https://pipeboard.co/api-tokens)
3. Include the token in HTTP headers:

```bash
curl -H "X-PIPEBOARD-API-TOKEN: your_pipeboard_token" \
     -X POST http://localhost:8080/mcp/ \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

### Alternative Method: Direct Meta Token

If you have a Meta Developer App, you can use a direct access token:

```bash
curl -H "X-META-ACCESS-TOKEN: your_meta_access_token" \
     -X POST http://localhost:8080/mcp/ \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## Available Endpoints

### Server URL Structure

**Base URL**: `http://localhost:8080`  
**MCP Endpoint**: `/mcp/`

### MCP Protocol Methods

| Method | Description |
|--------|-------------|
| `initialize` | Initialize MCP session and exchange capabilities |
| `tools/list` | Get list of all available Meta Ads tools (26 tools) |
| `tools/call` | Execute a specific tool with parameters |

### Response Format

All responses follow JSON-RPC 2.0 format:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    // Tool response data
  }
}
```

## Example Usage

### 1. Initialize Session

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -H "X-PIPEBOARD-API-TOKEN: your_token" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {"roots": {"listChanged": true}},
      "clientInfo": {"name": "my-app", "version": "1.0.0"}
    }
  }'
```

### 2. List Available Tools

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -H "X-PIPEBOARD-API-TOKEN: your_token" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 2
  }'
```

### 3. Get Ad Accounts

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -H "X-PIPEBOARD-API-TOKEN: your_token" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {
      "name": "get_ad_accounts",
      "arguments": {"limit": 10}
    }
  }'
```

### 4. Get Campaign Performance

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -H "X-PIPEBOARD-API-TOKEN: your_token" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 4,
    "params": {
      "name": "get_insights",
      "arguments": {
        "object_id": "act_701351919139047",
        "time_range": "last_30d",
        "level": "campaign"
      }
    }
  }'
```

## Client Examples

### Python Client

```python
import requests
import json

class MetaAdsMCPClient:
    def __init__(self, base_url="http://localhost:8080", token=None):
        self.base_url = base_url
        self.endpoint = f"{base_url}/mcp/"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if token:
            self.headers["X-PIPEBOARD-API-TOKEN"] = token
    
    def call_tool(self, tool_name, arguments=None):
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {"name": tool_name}
        }
        if arguments:
            payload["params"]["arguments"] = arguments
        
        response = requests.post(self.endpoint, headers=self.headers, json=payload)
        return response.json()

# Usage
client = MetaAdsMCPClient(token="your_pipeboard_token")
result = client.call_tool("get_ad_accounts", {"limit": 5})
print(json.dumps(result, indent=2))
```

### JavaScript/Node.js Client

```javascript
const axios = require('axios');

class MetaAdsMCPClient {
    constructor(baseUrl = 'http://localhost:8080', token = null) {
        this.baseUrl = baseUrl;
        this.endpoint = `${baseUrl}/mcp/`;
        this.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream'
        };
        if (token) {
            this.headers['X-PIPEBOARD-API-TOKEN'] = token;
        }
    }

    async callTool(toolName, arguments = null) {
        const payload = {
            jsonrpc: '2.0',
            method: 'tools/call',
            id: 1,
            params: { name: toolName }
        };
        if (arguments) {
            payload.params.arguments = arguments;
        }

        try {
            const response = await axios.post(this.endpoint, payload, { headers: this.headers });
            return response.data;
        } catch (error) {
            return { error: error.message };
        }
    }
}

// Usage
const client = new MetaAdsMCPClient('http://localhost:8080', 'your_pipeboard_token');
client.callTool('get_ad_accounts', { limit: 5 })
    .then(result => console.log(JSON.stringify(result, null, 2)));
```

## Production Deployment

### Security Considerations

1. **Use HTTPS**: In production, run behind a reverse proxy with SSL/TLS
2. **Authentication**: Always use valid Pipeboard or Meta access tokens
3. **Network Security**: Configure firewalls and access controls appropriately
4. **Rate Limiting**: Consider implementing rate limiting for public APIs

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . .
RUN pip install -e .

EXPOSE 8080

CMD ["python", "-m", "meta_ads_mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8080"]
```

### Environment Variables

```bash
# Required
PIPEBOARD_API_TOKEN=your_pipeboard_token

# Optional (for custom Meta apps)
META_APP_ID=your_app_id
META_APP_SECRET=your_app_secret
META_ACCESS_TOKEN=your_access_token
```

## Troubleshooting

### Common Issues

1. **Connection Refused**: Ensure the server is running and accessible on the specified port
2. **Authentication Failed**: Verify your Pipeboard token is valid and included in headers
3. **404 Not Found**: Make sure you're using the correct endpoint (`/mcp/`)
4. **JSON-RPC Errors**: Check that your request follows the JSON-RPC 2.0 format

### Debug Mode

Enable verbose logging:

```bash
python -m meta_ads_mcp --transport streamable-http --port 8080 --verbose
```

### Health Check

Test if the server is running:

```bash
curl -X POST http://localhost:8080/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

## Migration from stdio

If you're currently using stdio transport with MCP clients, you can run both modes simultaneously:

1. **Keep existing MCP client setup** (Claude Desktop, Cursor, etc.) using stdio
2. **Add HTTP transport** for web applications and custom integrations
3. **Use the same authentication** (Pipeboard token works for both)

Both transports access the same Meta Ads functionality and use the same authentication system. 