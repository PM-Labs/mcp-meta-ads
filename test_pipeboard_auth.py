#!/usr/bin/env python
"""
Test script for Meta Ads MCP authentication flow via Pipeboard.co.
This script shows how to authenticate with the Meta Ads API via Pipeboard.co and run a simple command.
"""

import os
import sys
import json
import asyncio
import argparse
import requests
import logging
import inspect
import socket

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("meta_ads_debug")

# Import only pipeboard auth manager to avoid META_APP_ID/META_APP_SECRET warnings
from meta_ads_mcp.core.pipeboard_auth import pipeboard_auth_manager, PIPEBOARD_API_BASE
from meta_ads_mcp.api import get_ad_accounts

# Define Meta Graph API base URL for testing access token directly
META_GRAPH_API_VERSION = "v22.0"
META_GRAPH_API_BASE = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}"

def test_server_connectivity(server_url, port=3000):
    """Test if the Pipeboard server is reachable and identify network issues"""
    logger.debug(f"Testing server connectivity to {server_url}")
    
    # Parse the URL
    from urllib.parse import urlparse
    parsed_url = urlparse(server_url)
    hostname = parsed_url.netloc.split(':')[0]
    
    # Test basic connectivity with socket
    try:
        logger.debug(f"Testing TCP connection to {hostname}:{port}")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((hostname, port))
        logger.debug(f"TCP connection successful to {hostname}:{port}")
        s.close()
    except socket.error as e:
        logger.error(f"Socket connection failed: {e}")
        return False
    
    # Test HTTP request to server root
    try:
        logger.debug(f"Testing HTTP request to {server_url}")
        response = requests.get(server_url, timeout=5)
        logger.debug(f"HTTP GET {server_url} response: {response.status_code}")
        
        if response.status_code == 200:
            logger.debug("Server is responding to HTTP requests")
            return True
        else:
            logger.error(f"Server returned HTTP {response.status_code}")
            logger.error(f"Response content: {response.text[:500]}")
            return False
    except requests.RequestException as e:
        logger.error(f"HTTP request failed: {e}")
        return False

async def test_token_manually(access_token):
    """Test the access token directly with Graph API to validate it"""
    logger.debug(f"Testing token directly with Graph API...")
    
    # Make a direct request to /me endpoint to check token
    me_url = f"{META_GRAPH_API_BASE}/me"
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(me_url, headers=headers)
        logger.debug(f"GET {me_url} response status: {response.status_code}")
        
        if response.status_code == 200:
            user_data = response.json()
            logger.debug(f"Token is valid. User ID: {user_data.get('id')}, Name: {user_data.get('name', 'N/A')}")
            return True
        else:
            logger.error(f"Token validation failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error validating token directly: {e}")
        return False

async def debug_pipeboard_token_endpoint(api_token):
    """Debug the Pipeboard token endpoint directly"""
    logger.debug(f"Debugging Pipeboard token endpoint...")
    # Pass token as URL parameter instead of Authorization header
    url = f"{PIPEBOARD_API_BASE}/meta/token?api_token={api_token}"
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        logger.debug(f"GET {url} response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # Mask token for logging
            if "access_token" in data:
                display_token = data["access_token"][:10] + "..." + data["access_token"][-5:]
                logger.debug(f"Token received: {display_token}")
                logger.debug(f"Token expires_at: {data.get('expires_at', 'Not provided')}")
                logger.debug(f"Token type: {data.get('token_type', 'Not provided')}")
            else:
                logger.error("No access_token in response")
            
            return data
        else:
            logger.error(f"Pipeboard token endpoint failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error calling Pipeboard token endpoint: {e}")
        return None

async def inspect_api_call_params(token):
    """Inspect what parameters are being sent to the Meta API in get_ad_accounts"""
    # This is using reflection to get source code of the get_ad_accounts function
    try:
        source = inspect.getsource(get_ad_accounts)
        logger.debug(f"get_ad_accounts function source:\n{source}")
    except Exception as e:
        logger.error(f"Error getting function source: {e}")

async def test_pipeboard_authentication(api_token=None, force_login=False, verbose=False, check_server=False):
    """Test the Pipeboard authentication flow and run a simple command"""
    print("===== Meta Ads MCP Authentication Test via Pipeboard.co =====")
    
    if verbose:
        print(f"Debug mode is ENABLED. Check logs for detailed information.")
    
    # Test server connectivity if requested
    if check_server:
        print("\nTesting server connectivity...")
        server_url = PIPEBOARD_API_BASE.rsplit('/api', 1)[0]  # Get base URL without /api
        if test_server_connectivity(server_url):
            print(f"✅ Pipeboard server at {server_url} is reachable")
        else:
            print(f"❌ CONNECTIVITY ERROR: Cannot reach Pipeboard server at {server_url}")
            print("Please check if the server is running and reachable from your machine.")
            print(f"Current PIPEBOARD_API_BASE is set to: {PIPEBOARD_API_BASE}")
            print("\nPossible issues:")
            print("1. Server is not running at the expected address")
            print("2. Firewall is blocking the connection")
            print("3. Network connectivity issues")
            print("4. Incorrect server URL in environment variables")
            return
    
    # Set the Pipeboard API token if provided
    if api_token:
        os.environ["PIPEBOARD_API_TOKEN"] = api_token
        logger.debug(f"Using provided Pipeboard API token: {api_token[:5]}...")
    else:
        # Check for token in environment
        api_token = os.environ.get("PIPEBOARD_API_TOKEN")
        if not api_token:
            logger.error("No Pipeboard API token provided. Please set PIPEBOARD_API_TOKEN environment variable or use --api-token")
            return
        logger.debug(f"Using Pipeboard API token from environment: {api_token[:5]}...")
    
    # Debug Pipeboard API URL
    logger.debug(f"Using Pipeboard API base URL: {PIPEBOARD_API_BASE}")
    
    # Force authentication if requested
    if force_login:
        logger.debug("Forcing new authentication...")
        try:
            # Invalidate any existing token first
            pipeboard_auth_manager.invalidate_token()
            logger.debug("Existing token invalidated")
            
            # Initiate the auth flow
            auth_data = pipeboard_auth_manager.initiate_auth_flow()
            login_url = auth_data.get("loginUrl")
            
            logger.debug(f"Auth flow initiated. Response: {auth_data}")
            print(f"\nPlease visit this URL to authorize with Meta: {login_url}")
            input("Press Enter after completing authorization in your browser...")
        except Exception as e:
            logger.error(f"Error initiating auth flow: {e}")
            return
    
    print("Getting access token (using cached token if available)...")
    
    # Debug the token endpoint directly
    pipeboard_token_data = await debug_pipeboard_token_endpoint(api_token)
    
    # Get token from auth manager
    token = pipeboard_auth_manager.get_access_token()
    
    if token:
        # Mask token for display
        masked_token = token[:10] + "..." + token[-5:]
        print(f"Access token obtained: {masked_token}")
        
        # Check token validity directly with Graph API
        logger.debug("Validating token directly with Meta Graph API...")
        token_valid = await test_token_manually(token)
        
        if not token_valid:
            print("\n⚠️ Token validation failed with Meta Graph API!")
            print("This may explain the 'Authentication Required' error.")
            
            # Check if token is from cache or fresh from API
            token_source = "cache" if pipeboard_auth_manager.token_info else "API"
            print(f"Token was obtained from: {token_source}")
            
            if token_source == "cache":
                print("\nTrying to force token refresh...")
                # Try to force refresh the token
                token = pipeboard_auth_manager.get_access_token(force_refresh=True)
                if token:
                    masked_token = token[:10] + "..." + token[-5:]
                    print(f"New access token obtained: {masked_token}")
                    token_valid = await test_token_manually(token)
                    if not token_valid:
                        print("⚠️ New token also invalid!")
        
        # Log token info
        if pipeboard_auth_manager.token_info:
            logger.debug(f"Token info - expires_at: {pipeboard_auth_manager.token_info.expires_at}")
            logger.debug(f"Token is_expired(): {pipeboard_auth_manager.token_info.is_expired()}")
            
        # Inspect API call parameters
        await inspect_api_call_params(token)
            
        # Test the token by getting ad accounts
        print("\nFetching ad accounts to test token...")
        logger.debug("Calling get_ad_accounts with token...")
        try:
            # Directly call the function with the token, not relying on the wrapper
            # to find it from auth manager
            ad_accounts_json = await get_ad_accounts(access_token=token, user_id="me", limit=10)
            logger.debug(f"API Response raw: {ad_accounts_json[:500]}...")
            
            try:
                ad_accounts = json.loads(ad_accounts_json)
                
                # Check for error response
                if isinstance(ad_accounts, dict) and ad_accounts.get("error"):
                    # Direct error message
                    if isinstance(ad_accounts["error"], str):
                        print(f"Error from Meta API: {ad_accounts['error']}")
                        logger.error(f"Error message: {ad_accounts['error']}")
                        
                        # Check for details
                        if "details" in ad_accounts and isinstance(ad_accounts["details"], dict):
                            error_details = ad_accounts["details"]
                            logger.error(f"Error details: {json.dumps(error_details, indent=2)}")
                            print(f"Error details: {error_details.get('message', 'No additional details')}")
                    # Error object
                    elif isinstance(ad_accounts["error"], dict):
                        error_info = ad_accounts["error"]
                        print(f"Error from Meta API: {error_info.get('message', 'Unknown error')}")
                        logger.error(f"Detailed error info: {json.dumps(error_info, indent=2)}")
                        
                        # Specific error handling for common issues
                        if "code" in error_info:
                            code = error_info.get("code")
                            if code == 190:
                                print("\n⚠️ Error 190: Invalid or expired access token")
                                print("This likely means your token has expired or been invalidated by Meta.")
                            elif code == 4:
                                print("\n⚠️ Error 4: Application request limit reached")
                                print("You have hit Meta's API rate limits.")
                            elif code == 200:
                                print("\n⚠️ Error 200: Permission error")
                                print("The token doesn't have permission for the requested operation.")
                    
                    # If there's a login_url in the response, show it
                    if "login_url" in ad_accounts:
                        print(f"\nPlease re-authenticate using this URL: {ad_accounts['login_url']}")
                    
                    # Look for markdown_link which may contain a clickable auth link
                    if "markdown_link" in ad_accounts:
                        print(f"\nAuthentication link: {ad_accounts['markdown_link']}")
                    
                    return
                
                if isinstance(ad_accounts, list):
                    print(f"Success! Found {len(ad_accounts)} ad accounts.")
                    for account in ad_accounts[:3]:  # Show first 3 accounts only
                        print(f"  - {account.get('name')} (ID: {account.get('id')})")
                    if len(ad_accounts) > 3:
                        print(f"  ... and {len(ad_accounts) - 3} more")
            except json.JSONDecodeError:
                print("Error parsing response from Meta API")
                print(f"Raw response: {ad_accounts_json[:100]}...")
                logger.error(f"JSON parse error on API response: {ad_accounts_json}")
                return
        except Exception as e:
            print(f"Exception when calling Meta API: {e}")
            logger.exception("Exception when calling Meta API")
    else:
        print("Failed to obtain access token. Authentication failed.")
        print("Please ensure you've completed the authorization process in your browser.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Meta Ads MCP authentication via Pipeboard.co")
    parser.add_argument("--api-token", type=str, help="Pipeboard API token for authentication")
    parser.add_argument("--force-login", action="store_true", help="Force new login even if cached token exists")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--check-server", action="store_true", help="Test server connectivity before proceeding")
    
    args = parser.parse_args()
    
    asyncio.run(test_pipeboard_authentication(
        api_token=args.api_token, 
        force_login=args.force_login, 
        verbose=args.verbose,
        check_server=args.check_server
    )) 