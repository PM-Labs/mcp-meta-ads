# Streamable HTTP Transport Implementation Analysis for Meta Ads MCP

## Overview

This document analyzes the requirements and security considerations for adding **Streamable HTTP** transport support to the Meta Ads MCP server. The focus is on the **primary Pipeboard authentication path**, with OAuth flow as a fallback for custom Meta app users.

## Authentication Architecture

### Primary Path: Pipeboard Authentication (90%+ of users)
- **Simple**: Single `PIPEBOARD_API_TOKEN` provides full access
- **Secure**: Pipeboard handles all OAuth complexity server-side
- **Maintained**: 60-day token refresh handled automatically
- **No local servers needed**: No callback servers or browser flows

### Fallback Path: Custom Meta App OAuth (minority of users)
- **Complex**: Requires local callback server and browser OAuth flow
- **Custom setup**: Users must create their own Meta Developer app
- **Manual token management**: Shorter-lived tokens, manual refresh
- **Only used when**: No Pipeboard token AND custom `META_APP_ID` provided

## Current Environment Variables

### Authentication Variables Currently Used

1. **Primary Authentication (Recommended):**
   - `PIPEBOARD_API_TOKEN` - Single token for full API access via Pipeboard

2. **Fallback Authentication (Custom Meta Apps):**
   - `META_APP_ID` - Meta Developer App ID for direct OAuth
   - `META_APP_SECRET` - Meta App Secret (for direct OAuth)
   - `META_ACCESS_TOKEN` - Direct access token (bypasses local cache)

3. **System Variables:**
   - `APPDATA` - Windows-specific path configuration (not relevant for HTTP headers)

## Security Analysis

### ✅ Safe for Streamable HTTP Headers

**Pipeboard API Token (`X-PIPEBOARD-API-TOKEN`) - PRIMARY METHOD:**
- **Security Level: HIGH** ✅
- **User Experience: SIMPLE** ✅
- Designed specifically for API access
- Built-in scoping and expiration
- Centrally managed and revocable
- No local OAuth complexity required
- **This handles 90%+ of use cases**

**Meta App ID (`X-META-APP-ID`) - FALLBACK ONLY:**
- **Security Level: MEDIUM-HIGH** ✅
- **User Experience: COMPLEX** ⚠️
- Semi-public identifier (appears in OAuth URLs)
- Required for OAuth URL generation (fallback path only)
- Only relevant for users with custom Meta Developer apps
- Triggers complex OAuth flow requiring local callback server

### ❌ Never via HTTP Headers

**Meta App Secret (`X-META-APP-SECRET`):**
- **Security Level: CRITICAL** ❌
- Too sensitive for HTTP transmission
- Server environment variables only

**Meta Access Token (`X-META-ACCESS-TOKEN`):**
- **Security Level: HIGH RISK** ❌
- Should use proper authentication flows instead

## Streamable HTTP Transport Benefits

### Advantages over SSE
- **Stateless operation** - No session state management required
- **Resumability with event stores** - Better reliability for long-running operations
- **JSON response format** - Clean, standard API responses
- **Better scalability** - Designed for multi-node deployments
- **Modern standard** - Actively developed and supported by MCP

## Implementation Strategy

### 1. Command Line Interface Changes

Add transport selection and Streamable HTTP-specific options:

```python
parser.add_argument("--transport", type=str, choices=["stdio", "streamable-http"], 
                   default="stdio", help="Transport method (default: stdio)")
parser.add_argument("--port", type=int, default=8080, 
                   help="Port for Streamable HTTP transport (default: 8080)")
parser.add_argument("--host", type=str, default="localhost", 
                   help="Host for Streamable HTTP transport (default: localhost)")
parser.add_argument("--sse-response", action="store_true", 
                   help="Use SSE response format instead of JSON (default: JSON)")
```

### 2. Simplified Header-Based Configuration

**Primary Path - Pipeboard (Simple):**
```python
def get_auth_config_from_headers(request_headers):
    """Extract authentication configuration from HTTP headers"""
    
    # PRIMARY: Check for Pipeboard token (handles 90%+ of cases)
    pipeboard_token = request_headers.get('X-PIPEBOARD-API-TOKEN')
    if pipeboard_token:
        return {
            'auth_method': 'pipeboard',
            'pipeboard_api_token': pipeboard_token,
            'requires_oauth': False  # Simple token-based auth
        }
    
    # FALLBACK: Custom Meta app (minority of users)
    meta_app_id = request_headers.get('X-META-APP-ID')
    if meta_app_id:
        return {
            'auth_method': 'custom_meta_app',
            'meta_app_id': meta_app_id,
            'requires_oauth': True  # Complex OAuth flow required
        }
    
    # No authentication provided
    return {
        'auth_method': 'none',
        'requires_oauth': False
    }

# Security validation
ALLOWED_VIA_HEADERS = {
    'pipeboard_api_token': True,   # ✅ Primary method - simple and secure
    'meta_app_id': True,           # ✅ Fallback only - triggers OAuth complexity
    'meta_app_secret': False,      # ❌ Server environment only
    'meta_access_token': False,    # ❌ Use proper auth flows instead
}
```

### 3. Stateless Request Handling

```python
class StreamableHTTPHandler:
    """Handles stateless Streamable HTTP requests"""
    
    def __init__(self):
        # No session storage - all auth per request
        pass
    
    def handle_request(self, request_headers, request_body):
        """Handle individual request with authentication"""
        auth_config = get_auth_config_from_headers(request_headers)
        
        # Handle based on auth method
        if auth_config['auth_method'] == 'pipeboard':
            # Simple case - token provides direct access
            return self.handle_pipeboard_request(auth_config, request_body)
            
        elif auth_config['auth_method'] == 'custom_meta_app':
            # Complex case - may require OAuth flow initiation
            return self.handle_custom_app_request(auth_config, request_body)
            
        else:
            # No auth provided
            return self.handle_unauthenticated_request(request_body)
    
    def handle_pipeboard_request(self, auth_config, request_body):
        """Handle request with Pipeboard token (primary path)"""
        token = auth_config['pipeboard_api_token']
        # Token is ready to use immediately for API calls
        return {
            'status': 'ready',
            'auth_method': 'pipeboard',
            'access_token': token
        }
    
    def handle_custom_app_request(self, auth_config, request_body):
        """Handle request with custom Meta app (fallback path)"""
        # This may require OAuth flow initiation
        # Each request is independent - no session state
        return {
            'status': 'oauth_required',
            'auth_method': 'custom_meta_app',
            'meta_app_id': auth_config['meta_app_id']
        }
```

### 4. Authentication Flow (Simplified for Majority)

```python
async def handle_authentication(request_headers):
    """Handle authentication based on method (stateless)"""
    
    auth_config = get_auth_config_from_headers(request_headers)
    
    if auth_config['auth_method'] == 'pipeboard':
        # PRIMARY PATH: Simple token validation
        token = auth_config['pipeboard_api_token']
        # Token is ready to use immediately
        return {
            'status': 'ready',
            'auth_method': 'pipeboard',
            'token_source': 'pipeboard',
            'access_token': token
        }
    
    elif auth_config['auth_method'] == 'custom_meta_app':
        # FALLBACK PATH: Complex OAuth flow
        # Only executed for minority of users with custom Meta apps
        return await initiate_custom_oauth_flow(auth_config)
    
    else:
        return {
            'status': 'error',
            'message': 'No authentication method provided',
            'supported_methods': ['pipeboard_token', 'custom_meta_app']
        }

async def initiate_custom_oauth_flow(auth_config):
    """Fallback OAuth flow for custom Meta app users (minority)"""
    # This is the complex path that requires local callback server
    # Most users will never hit this code path
    
    # Configure auth_manager for custom app
    auth_manager.app_id = auth_config['meta_app_id']
    
    # Start callback server and generate OAuth URL
    port = start_callback_server()
    auth_manager.redirect_uri = f"http://localhost:{port}/callback"
    oauth_url = auth_manager.get_auth_url()
    
    return {
        'status': 'oauth_required',
        'auth_method': 'custom_meta_app',
        'oauth_url': oauth_url,
        'callback_port': port,
        'message': 'Complete OAuth flow in browser (custom Meta app users only)'
    }
```

### 5. Server Startup Modification

```python
def main():
    """Main entry point with Streamable HTTP transport support"""
    # ... existing argument parsing ...
    
    parser.add_argument("--transport", type=str, choices=["stdio", "streamable-http"], 
                       default="stdio", help="Transport method")
    parser.add_argument("--port", type=int, default=8080, help="Streamable HTTP port")
    parser.add_argument("--host", type=str, default="localhost", help="Streamable HTTP host")
    parser.add_argument("--sse-response", action="store_true", help="Use SSE instead of JSON")
    
    args = parser.parse_args()
    
    # ... existing configuration logic ...
    
    if args.transport == "streamable-http":
        logger.info(f"Starting MCP server with Streamable HTTP transport on {args.host}:{args.port}")
        logger.info("Mode: Stateless (no session persistence)")
        logger.info(f"Response format: {'SSE' if args.sse_response else 'JSON'}")
        logger.info("Primary auth method: Pipeboard API Token (recommended)")
        logger.info("Fallback auth method: Custom Meta App OAuth (complex setup)")
        
        # Create server with stateless configuration
        global mcp_server
        mcp_server = FastMCP(
            "meta-ads", 
            use_consistent_tool_format=True,
            stateless_http=True,  # Always stateless
            json_response=not args.sse_response  # JSON by default
        )
        
        # Re-register resources and tools
        mcp_server.resource(uri="meta-ads://resources")(list_resources)
        mcp_server.resource(uri="meta-ads://images/{resource_id}")(get_resource)
        
        mcp_server.run(transport="streamable-http", port=args.port, host=args.host)
    else:
        mcp_server.run(transport='stdio')
```

## Security Recommendations

### 1. Stateless Security Model

```python
# Streamlined security configuration for stateless operation
STREAMABLE_HTTP_SECURITY_CONFIG = {
    'primary_auth_method': 'pipeboard',  # Simple token-based
    'fallback_auth_method': 'custom_meta_app',  # Complex OAuth
    
    'allowed_headers': [
        'X-PIPEBOARD-API-TOKEN',  # ✅ Primary - simple and secure
        'X-META-APP-ID'           # ✅ Fallback - triggers OAuth complexity
    ],
    
    'require_https': True,
    'rate_limiting': True,
    'stateless_only': True,  # No session persistence
    'json_response': True    # Default to JSON responses
}
```

### 2. Client Configuration Examples

**Primary Path - Simple Pipeboard (90%+ of users):**
```javascript
// Simple authentication with Pipeboard token - JSON response
const response = await fetch('/mcp', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-PIPEBOARD-API-TOKEN': 'your_pipeboard_token'
        // That's it! No OAuth complexity needed
    },
    body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'tools/call',
        params: { name: 'get_campaigns', arguments: {} },
        id: 1
    })
});

// Clean JSON response
const result = await response.json();
console.log(result); // Standard JSON-RPC response
```

**Fallback Path - Custom Meta App (minority of users):**
```javascript
// Complex authentication for custom Meta app users
const response = await fetch('/mcp', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-META-APP-ID': 'your_custom_meta_app_id'
        // This will trigger OAuth flow requirement
    },
    body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'tools/call',
        params: { name: 'get_login_link', arguments: {} },
        id: 1
    })
});

// JSON response will include OAuth URL for browser completion
const result = await response.json();
// Much more complex flow for minority of users
```

## Implementation Benefits

### Primary Path Advantages (Pipeboard)
1. **Simple setup** - Single token configuration
2. **No local servers** - No callback server complexity
3. **Long-lived tokens** - 60-day refresh cycle
4. **Centrally managed** - Revocation and monitoring via Pipeboard
5. **No browser flows** - No OAuth redirect complexity
6. **Stateless scaling** - Each request independent
7. **Clean JSON responses** - Standard web API format

### Fallback Path (Custom Meta Apps)
1. **Full control** - Users own their Meta app
2. **Direct Meta API** - No intermediary service
3. **Custom scopes** - Can request specific permissions
4. **Advanced use cases** - For users with special requirements

### Scalability Benefits
1. **Horizontal scaling** - No session state to maintain
2. **Load balancer friendly** - Any server can handle any request
3. **Simple deployment** - No shared session storage required
4. **Better performance** - No session lookup overhead
5. **Standard JSON** - Easy integration with web frameworks and tools

## Migration Path

### Phase 1: Basic Streamable HTTP Support
- Add transport flag and Streamable HTTP server setup
- Implement simple Pipeboard token authentication (primary path)
- Basic header parsing with security validation
- Stateless request handling with JSON responses

### Phase 2: Fallback OAuth Support
- Add custom Meta app authentication (fallback path only)
- Implement OAuth flow for minority of users
- Ensure OAuth complexity doesn't affect primary users

### Phase 3: Production Hardening
- Add HTTPS enforcement
- Implement rate limiting and security headers
- Enhanced logging distinguishing between auth methods
- Performance optimization for stateless operation

## Conclusion

Adding Streamable HTTP transport to Meta Ads MCP should prioritize simplicity and scalability:

1. **Primary Path (90%+ users)**: Simple Pipeboard token via `X-PIPEBOARD-API-TOKEN`
   - No OAuth complexity
   - No local callback servers
   - Single header authentication
   - Stateless operation
   - Clean JSON responses

2. **Fallback Path (minority)**: Custom Meta app OAuth via `X-META-APP-ID`
   - Complex OAuth flow
   - Local callback server required
   - Browser-based authentication

3. **Stateless Architecture**: 
   - Better scalability and performance
   - Simpler deployment and maintenance
   - Load balancer friendly

4. **JSON-First Design**:
   - Standard web API responses
   - Easy integration with modern tools
   - Better developer experience

5. **Security**: Only allow safe headers, leverage existing auth infrastructure

This design ensures the majority of users have a simple experience while providing excellent scalability and maintaining support for advanced users who need custom Meta app integration. 