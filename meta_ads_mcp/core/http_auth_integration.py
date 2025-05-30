"""
FastMCP HTTP Authentication Integration for Meta Ads MCP

This module provides direct integration with FastMCP to inject authentication
from HTTP headers into the tool execution context.
"""

import asyncio
import contextvars
from typing import Optional
from .utils import logger

# Use context variables instead of thread-local storage for better async support
_auth_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('auth_token', default=None)

class FastMCPAuthIntegration:
    """Direct integration with FastMCP for HTTP authentication"""
    
    @staticmethod
    def set_auth_token(token: str) -> None:
        """Set authentication token for the current context
        
        Args:
            token: Access token to use for this request
        """
        _auth_token.set(token)
        logger.debug(f"Set auth token in context: {token[:10]}...")
    
    @staticmethod
    def get_auth_token() -> Optional[str]:
        """Get authentication token for the current context
        
        Returns:
            Access token if set, None otherwise
        """
        return _auth_token.get(None)
    
    @staticmethod
    def clear_auth_token() -> None:
        """Clear authentication token for the current context"""
        _auth_token.set(None)
        logger.debug("Cleared auth token from context")
    
    @staticmethod
    def extract_token_from_headers(headers: dict) -> Optional[str]:
        """Extract token from HTTP headers
        
        Args:
            headers: HTTP request headers
            
        Returns:
            Token if found, None otherwise
        """
        # Check for Pipeboard token (primary method)
        pipeboard_token = headers.get('X-PIPEBOARD-API-TOKEN') or headers.get('x-pipeboard-api-token')
        if pipeboard_token:
            logger.debug("Found Pipeboard token in headers")
            return pipeboard_token
        
        # Check for direct Meta access token
        meta_token = headers.get('X-META-ACCESS-TOKEN') or headers.get('x-meta-access-token')
        if meta_token:
            logger.debug("Found Meta access token in headers")
            return meta_token
        
        return None

def patch_fastmcp_server(mcp_server):
    """Patch FastMCP server to inject authentication from HTTP headers
    
    Args:
        mcp_server: FastMCP server instance to patch
    """
    logger.info("Patching FastMCP server for HTTP authentication")
    
    # Store the original run method
    original_run = mcp_server.run
    
    def patched_run(transport="stdio", **kwargs):
        """Enhanced run method that sets up HTTP auth integration"""
        logger.info(f"Starting FastMCP with transport: {transport}")
        
        if transport == "streamable-http":
            logger.info("Setting up HTTP authentication for streamable-http transport")
            setup_http_auth_patching()
        
        # Call the original run method
        return original_run(transport=transport, **kwargs)
    
    # Replace the run method
    mcp_server.run = patched_run
    logger.info("FastMCP server patching complete")

def setup_http_auth_patching():
    """Setup HTTP authentication patching for auth system"""
    logger.info("Setting up HTTP authentication patching")
    
    # Import and patch the auth system
    from . import auth
    from . import api
    from . import authentication
    
    # Store the original function
    original_get_current_access_token = auth.get_current_access_token
    
    async def get_current_access_token_with_http_support() -> Optional[str]:
        """Enhanced get_current_access_token that checks HTTP context first"""
        
        # Check for context-scoped token first
        context_token = FastMCPAuthIntegration.get_auth_token()
        if context_token:
            logger.debug("Using token from HTTP context")
            return context_token
        
        # Fall back to original implementation
        return await original_get_current_access_token()
    
    # Replace the function in all modules that imported it
    auth.get_current_access_token = get_current_access_token_with_http_support
    api.get_current_access_token = get_current_access_token_with_http_support
    authentication.get_current_access_token = get_current_access_token_with_http_support
    
    logger.info("Auth system patching complete - patched in auth, api, and authentication modules")

# Global instance for easy access
fastmcp_auth = FastMCPAuthIntegration()

def setup_fastmcp_http_auth(mcp_server):
    """Setup HTTP authentication integration with FastMCP
    
    Args:
        mcp_server: FastMCP server instance to configure
    """
    logger.info("Setting up FastMCP HTTP authentication integration")
    
    # Patch the server to handle HTTP authentication
    patch_fastmcp_server(mcp_server)
    
    # Try to patch the actual HTTP request handling if we can access it
    try:
        # This is experimental - try to hook into FastMCP's internal request processing
        setup_request_middleware(mcp_server)
    except Exception as e:
        logger.warning(f"Could not setup request middleware: {e}")
        logger.info("Using fallback authentication approach")
    
    logger.info("FastMCP HTTP authentication integration ready")

def setup_request_middleware(mcp_server):
    """Setup middleware to inject authentication into request context
    
    Args:
        mcp_server: FastMCP server instance
    """
    logger.info("Setting up request middleware for authentication injection")
    
    # This is where we'd hook into FastMCP's request processing
    # For now, we'll use the context variable approach with manual injection
    
    # Try to access FastMCP's internal app/server
    if hasattr(mcp_server, '_app') or hasattr(mcp_server, 'app'):
        app = getattr(mcp_server, '_app', None) or getattr(mcp_server, 'app', None)
        
        if app:
            logger.info("Found FastMCP app instance, attempting middleware injection")
            try:
                setup_starlette_middleware(app)
            except Exception as e:
                logger.warning(f"Starlette middleware setup failed: {e}")
    
    logger.info("Request middleware setup complete")

def setup_starlette_middleware(app):
    """Setup Starlette middleware for authentication
    
    Args:
        app: Starlette app instance
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    
    class AuthInjectionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Extract auth token from headers
            token = FastMCPAuthIntegration.extract_token_from_headers(dict(request.headers))
            
            if token:
                logger.debug("Injecting auth token into request context")
                FastMCPAuthIntegration.set_auth_token(token)
            
            try:
                response = await call_next(request)
                return response
            finally:
                # Clean up after request
                if token:
                    FastMCPAuthIntegration.clear_auth_token()
    
    # Add our middleware to the app
    app.add_middleware(AuthInjectionMiddleware)
    logger.info("Starlette auth middleware added successfully") 