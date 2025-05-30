"""MCP server configuration for Meta Ads API."""

from mcp.server.fastmcp import FastMCP
import argparse
import os
import sys
import webbrowser
from .auth import login as login_auth
from .resources import list_resources, get_resource
from .utils import logger
from .pipeboard_auth import pipeboard_auth_manager
import time

# Initialize FastMCP server
mcp_server = FastMCP("meta-ads", use_consistent_tool_format=True)

# Register resource URIs
mcp_server.resource(uri="meta-ads://resources")(list_resources)
mcp_server.resource(uri="meta-ads://images/{resource_id}")(get_resource)

def login_cli():
    """
    Command-line function to authenticate with Meta
    """
    logger.info("Starting Meta Ads CLI authentication flow")
    print("Starting Meta Ads CLI authentication flow...")
    
    # Call the common login function
    login_auth()


def main():
    """Main entry point for the package"""
    # Log startup information
    logger.info("Meta Ads MCP server starting")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Args: {sys.argv}")
    
    # Initialize argument parser
    parser = argparse.ArgumentParser(
        description="Meta Ads MCP Server - Model Context Protocol server for Meta Ads API",
        epilog="For more information, see https://github.com/pipeboard-co/meta-ads-mcp"
    )
    parser.add_argument("--login", action="store_true", help="Authenticate with Meta and store the token")
    parser.add_argument("--app-id", type=str, help="Meta App ID (Client ID) for authentication")
    parser.add_argument("--version", action="store_true", help="Show the version of the package")
    
    # Transport configuration arguments
    parser.add_argument("--transport", type=str, choices=["stdio", "streamable-http"], 
                       default="stdio", 
                       help="Transport method: 'stdio' for MCP clients (default), 'streamable-http' for HTTP API access")
    parser.add_argument("--port", type=int, default=8080, 
                       help="Port for Streamable HTTP transport (default: 8080, only used with --transport streamable-http)")
    parser.add_argument("--host", type=str, default="localhost", 
                       help="Host for Streamable HTTP transport (default: localhost, only used with --transport streamable-http)")
    parser.add_argument("--sse-response", action="store_true", 
                       help="Use SSE response format instead of JSON (default: JSON, only used with --transport streamable-http)")
    
    args = parser.parse_args()
    logger.info(f"Parsed args: login={args.login}, app_id={args.app_id}, version={args.version}")
    logger.info(f"Transport args: transport={args.transport}, port={args.port}, host={args.host}, sse_response={args.sse_response}")
    
    # Validate CLI argument combinations
    if args.transport == "stdio" and (args.port != 8080 or args.host != "localhost" or args.sse_response):
        logger.warning("HTTP transport arguments (--port, --host, --sse-response) are ignored when using stdio transport")
        print("Warning: HTTP transport arguments are ignored when using stdio transport")
    
    # Update app ID if provided as environment variable or command line arg
    from .auth import auth_manager, meta_config
    
    # Check environment variable first (early init)
    env_app_id = os.environ.get("META_APP_ID")
    if env_app_id:
        logger.info(f"Found META_APP_ID in environment: {env_app_id}")
    else:
        logger.warning("META_APP_ID not found in environment variables")
    
    # Command line takes precedence
    if args.app_id:
        logger.info(f"Setting app_id from command line: {args.app_id}")
        auth_manager.app_id = args.app_id
        meta_config.set_app_id(args.app_id)
    elif env_app_id:
        logger.info(f"Setting app_id from environment: {env_app_id}")
        auth_manager.app_id = env_app_id
        meta_config.set_app_id(env_app_id)
    
    # Log the final app ID that will be used
    logger.info(f"Final app_id from meta_config: {meta_config.get_app_id()}")
    logger.info(f"Final app_id from auth_manager: {auth_manager.app_id}")
    logger.info(f"ENV META_APP_ID: {os.environ.get('META_APP_ID')}")
    
    # Show version if requested
    if args.version:
        from meta_ads_mcp import __version__
        logger.info(f"Displaying version: {__version__}")
        print(f"Meta Ads MCP v{__version__}")
        return 0
    
    # Handle login command
    if args.login:
        login_cli()
        return 0
    
    # Check for Pipeboard authentication and token
    pipeboard_api_token = os.environ.get("PIPEBOARD_API_TOKEN")
    if pipeboard_api_token:
        logger.info("Using Pipeboard authentication")
        # Check for existing token
        token = pipeboard_auth_manager.get_access_token()
        if not token:
            logger.info("No valid Pipeboard token found. Initiating browser-based authentication flow.")
            print("No valid Meta token found. Opening browser for authentication...")
            try:
                # Initialize the auth flow and get the login URL
                auth_data = pipeboard_auth_manager.initiate_auth_flow()
                login_url = auth_data.get('loginUrl')
                if login_url:
                    logger.info(f"Opening browser with login URL: {login_url}")
                    webbrowser.open(login_url)
                    print("Please authorize the application in your browser.")
                    print("After authorization, the token will be automatically retrieved.")
                    print("Waiting for authentication to complete...")
                    
                    # Poll for token completion
                    max_attempts = 30  # Try for 30 * 2 = 60 seconds
                    for attempt in range(max_attempts):
                        print(f"Waiting for authentication... ({attempt+1}/{max_attempts})")
                        # Try to get the token again
                        token = pipeboard_auth_manager.get_access_token(force_refresh=True)
                        if token:
                            print("Authentication successful!")
                            break
                        time.sleep(2)  # Wait 2 seconds between attempts
                    
                    if not token:
                        print("Authentication timed out. Starting server anyway.")
                        print("You may need to restart the server after completing authentication.")
                else:
                    logger.error("No login URL received from Pipeboard API")
                    print("Error: Could not get authentication URL. Check your API token.")
            except Exception as e:
                logger.error(f"Error initiating browser-based authentication: {e}")
                print(f"Error: Could not start authentication: {e}")
    
    # Transport-specific server initialization and startup
    if args.transport == "streamable-http":
        logger.info(f"Starting MCP server with Streamable HTTP transport on {args.host}:{args.port}")
        logger.info("Mode: Stateless (no session persistence)")
        logger.info(f"Response format: {'SSE' if args.sse_response else 'JSON'}")
        logger.info("Primary auth method: Pipeboard API Token (recommended)")
        logger.info("Fallback auth method: Custom Meta App OAuth (complex setup)")
        
        print(f"Starting Meta Ads MCP server with Streamable HTTP transport")
        print(f"Server will listen on {args.host}:{args.port}")
        print(f"Response format: {'SSE' if args.sse_response else 'JSON'}")
        print("Primary authentication: Pipeboard API Token (via X-PIPEBOARD-API-TOKEN header)")
        print("Fallback authentication: Custom Meta App OAuth (via X-META-APP-ID header)")
        
        # TODO: Initialize Streamable HTTP server configuration
        # This will be implemented in the next phase
        logger.error("Streamable HTTP transport not yet implemented")
        print("Error: Streamable HTTP transport is not yet implemented.")
        print("Please use --transport stdio (default) for now.")
        return 1
    else:
        # Default stdio transport
        logger.info("Starting MCP server with stdio transport")
        mcp_server.run(transport='stdio') 