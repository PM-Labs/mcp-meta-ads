#!/usr/bin/env python
"""
A modified version of the meta_api_tool wrapper function with enhanced debugging
to understand how tokens are managed.
"""

import os
import asyncio
import json
import logging
import inspect
from functools import wraps
from typing import Any, Dict, Optional

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("meta_api_wrapper_debug")

# Import needed components
from meta_ads_mcp.core.pipeboard_auth import pipeboard_auth_manager
from meta_ads_mcp.api import get_ad_accounts

# Flag to track if authentication is needed
needs_authentication = False

async def debug_get_current_access_token() -> Optional[str]:
    """
    Debug version of get_current_access_token with detailed logging
    """
    logger.debug("debug_get_current_access_token called")
    
    # Try to get token from pipeboard_auth_manager
    if pipeboard_auth_manager:
        token = pipeboard_auth_manager.get_access_token()
        if token:
            logger.debug(f"Token retrieved from pipeboard_auth_manager: {token[:10]}...{token[-5:]}")
            return token
        else:
            logger.debug("No token returned from pipeboard_auth_manager")
    else:
        logger.debug("pipeboard_auth_manager is not available")
    
    logger.debug("Returning None from debug_get_current_access_token")
    return None

def debug_meta_api_tool(func):
    """Debugging version of meta_api_tool decorator with enhanced logging"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        global needs_authentication
        
        logger.debug(f"debug_meta_api_tool wrapper called for {func.__name__}")
        logger.debug(f"Args: {args}")
        logger.debug(f"Kwargs: {kwargs}")
        
        # Handle various MCP invocation patterns
        if len(args) == 1:
            logger.debug("Single argument detected, checking type")
            # MCP might pass a single string argument that contains JSON
            if isinstance(args[0], str):
                logger.debug(f"String argument: {args[0][:50]}...")
                try:
                    # Try to parse the single string argument as JSON dictionary
                    parsed_kwargs = json.loads(args[0]) if args[0] else {}
                    logger.debug(f"Parsed string to JSON: {parsed_kwargs}")
                    # Clear args and use parsed_kwargs
                    args = ()
                    kwargs.update(parsed_kwargs)
                    logger.debug(f"Updated kwargs: {kwargs}")
                except Exception as e:
                    logger.debug(f"JSON parsing error: {e}")
            # MCP might also pass a single dictionary argument
            elif isinstance(args[0], dict):
                logger.debug(f"Dict argument: {args[0]}")
                # Treat the dict as kwargs
                kwargs.update(args[0])
                args = ()
                logger.debug(f"Updated kwargs from dict: {kwargs}")
        
        # Check if we have a 'kwargs' parameter, which means MCP is nesting the real parameters
        if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], (str, dict)):
            logger.debug("'kwargs' parameter found in kwargs")
            # If it's a string, try to parse as JSON
            if isinstance(kwargs['kwargs'], str):
                logger.debug(f"'kwargs' is a string: {kwargs['kwargs'][:50]}...")
                try:
                    parsed_inner_kwargs = json.loads(kwargs['kwargs']) if kwargs['kwargs'] else {}
                    logger.debug(f"Parsed inner_kwargs: {parsed_inner_kwargs}")
                    kwargs.update(parsed_inner_kwargs)
                except Exception as e:
                    logger.debug(f"Inner JSON parsing error: {e}")
                    # If parsing fails, just keep the original kwargs
                    pass
            # If it's already a dict, just update kwargs
            elif isinstance(kwargs['kwargs'], dict):
                logger.debug(f"'kwargs' is a dict: {kwargs['kwargs']}")
                kwargs.update(kwargs['kwargs'])
            
            # Remove the 'kwargs' parameter to avoid confusion
            del kwargs['kwargs']
            logger.debug(f"Updated kwargs after processing nested kwargs: {kwargs}")
            
        # Handle 'args' parameter if it exists
        if 'args' in kwargs:
            logger.debug("'args' parameter found in kwargs, removing it")
            # We don't use positional args, so just remove it
            del kwargs['args']
        
        # Check if access_token is provided in kwargs
        access_token = kwargs.get('access_token')
        if access_token:
            logger.debug(f"access_token found in kwargs: {access_token[:10]}...{access_token[-5:]}")
        else:
            logger.debug("No access_token found in kwargs, trying to get from auth manager")
        
        # If not, try to get it from the auth manager
        if not access_token:
            access_token = await debug_get_current_access_token()
            if access_token:
                logger.debug(f"Token retrieved from debug_get_current_access_token: {access_token[:10]}...{access_token[-5:]}")
                kwargs['access_token'] = access_token
                logger.debug("Added access_token to kwargs")
            else:
                logger.debug("No token returned from debug_get_current_access_token")
        
        # If still no token, we need authentication
        if not access_token:
            logger.debug("No access_token available, setting needs_authentication=True")
            needs_authentication = True
            
            # Check if we're using Pipeboard authentication
            using_pipeboard = bool(os.environ.get("PIPEBOARD_API_TOKEN", ""))
            logger.debug(f"Using Pipeboard authentication: {using_pipeboard}")
            
            if using_pipeboard:
                # For Pipeboard, we use a different authentication flow
                try:
                    logger.debug("Initiating Pipeboard auth flow")
                    # Here we'd import dynamically to avoid circular imports
                    # Already imported pipeboard_auth_manager at the top
                    
                    # Initiate the Pipeboard auth flow
                    auth_data = pipeboard_auth_manager.initiate_auth_flow()
                    login_url = auth_data.get("loginUrl")
                    logger.debug(f"Auth flow initiated, login URL: {login_url[:50]}...")
                    
                    # Return a user-friendly authentication required response for Pipeboard
                    response = {
                        "error": "Authentication Required",
                        "details": {
                            "message": "You need to authenticate with the Meta API via Pipeboard",
                            "action_required": "Please authenticate using the link below",
                            "login_url": login_url,
                            "markdown_link": f"[Click here to authenticate with Meta Ads API via Pipeboard]({login_url})",
                            "authentication_method": "pipeboard"
                        }
                    }
                    logger.debug(f"Returning authentication required response: {response}")
                    return json.dumps(response, indent=2)
                except Exception as e:
                    logger.error(f"Error initiating Pipeboard auth flow: {e}")
                    response = {
                        "error": f"Pipeboard Authentication Error: {str(e)}",
                        "details": {
                            "message": "Failed to initiate Pipeboard authentication flow",
                            "action_required": "Please check your PIPEBOARD_API_TOKEN environment variable"
                        }
                    }
                    logger.debug(f"Returning error response: {response}")
                    return json.dumps(response, indent=2)
        
        # Call the original function
        try:
            logger.debug(f"Calling original function {func.__name__} with kwargs: {kwargs}")
            result = await func(**kwargs)
            logger.debug(f"Original function returned result type: {type(result)}")
            
            # If authentication is needed after the call (e.g., token was invalidated)
            if needs_authentication:
                logger.debug("needs_authentication flag is True after function call")
                # Similar authentication logic as above...
                # (omitted for brevity, add back in if needed)
                pass
            
            return result
        except Exception as e:
            logger.error(f"Error calling original function: {e}")
            # Handle any unexpected errors
            error_result = {
                "error": f"Error calling Meta API: {str(e)}"
            }
            return json.dumps(error_result, indent=2)
    
    return wrapper

async def test_debug_wrapper():
    """Test function to demonstrate the debug wrapper"""
    # Apply our debug wrapper to get_ad_accounts
    debug_wrapped_get_ad_accounts = debug_meta_api_tool(get_ad_accounts.__wrapped__)
    
    print("===== Testing Debug Meta API Tool Wrapper =====")
    
    print("\n1. Calling without explicit token:")
    try:
        result = await debug_wrapped_get_ad_accounts()
        print(f"Result type: {type(result)}")
        if isinstance(result, str):
            data = json.loads(result)
            if "error" in data:
                print(f"Error: {data['error']}")
            elif isinstance(data, list):
                print(f"Success! Found {len(data)} items.")
            else:
                print(f"Unexpected result format: {type(data)}")
    except Exception as e:
        print(f"Error in call: {e}")
    
    # Get a token directly from pipeboard_auth_manager
    print("\n2. Getting token directly from pipeboard_auth_manager:")
    token = pipeboard_auth_manager.get_access_token()
    if token:
        print(f"Token: {token[:10]}...{token[-5:]}")
        
        print("\n3. Calling with explicit token:")
        try:
            result = await debug_wrapped_get_ad_accounts(access_token=token)
            print(f"Result type: {type(result)}")
            if isinstance(result, str):
                data = json.loads(result)
                if "error" in data:
                    print(f"Error: {data['error']}")
                elif isinstance(data, list):
                    print(f"Success! Found {len(data)} items.")
                else:
                    print(f"Unexpected result format: {type(data)}")
        except Exception as e:
            print(f"Error in call with token: {e}")
    else:
        print("No token available")
    
    print("\n4. Global state:")
    print(f"needs_authentication: {needs_authentication}")

if __name__ == "__main__":
    asyncio.run(test_debug_wrapper()) 