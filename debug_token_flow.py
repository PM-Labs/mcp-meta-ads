#!/usr/bin/env python
"""
Debug script to verify token flow between pipeboard_auth_manager and the meta_api_tool wrapper.
This script will help us understand how tokens are being passed and used throughout the system.
"""

import os
import sys
import json
import asyncio
import logging
import inspect
from pprint import pprint

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("token_flow_debug")

# Import the auth modules and API functions
from meta_ads_mcp.core.pipeboard_auth import pipeboard_auth_manager, PIPEBOARD_API_BASE
from meta_ads_mcp.api import get_ad_accounts, auth_manager, get_current_access_token, meta_api_tool, needs_authentication

# Get the original get_ad_accounts function before it's wrapped
original_get_ad_accounts = None
for attr_name in dir(get_ad_accounts):
    if attr_name == "__wrapped__":
        original_get_ad_accounts = getattr(get_ad_accounts, attr_name)
        break

async def debug_token_flow():
    """Test and debug the token flow between different components"""
    print("===== Token Flow Debugging =====")
    
    # 1. Check if PIPEBOARD_API_TOKEN is set
    api_token = os.environ.get("PIPEBOARD_API_TOKEN")
    if not api_token:
        print("No PIPEBOARD_API_TOKEN environment variable set. Please set it first.")
        return
    
    print(f"Using Pipeboard API token: {api_token[:5]}...")
    print(f"Pipeboard API base URL: {PIPEBOARD_API_BASE}")
    
    # 2. Get token from pipeboard_auth_manager
    print("\n--- Step 1: Get token from pipeboard_auth_manager ---")
    pipeboard_token = pipeboard_auth_manager.get_access_token()
    
    if pipeboard_token:
        print(f"Token from pipeboard_auth_manager: {pipeboard_token[:10]}...{pipeboard_token[-5:]}")
        print(f"Token type: {type(pipeboard_token)}")
        print(f"Token length: {len(pipeboard_token)}")
        
        # Check token info object
        if pipeboard_auth_manager.token_info:
            print(f"Token expires_at: {pipeboard_auth_manager.token_info.expires_at}")
            print(f"Token is_expired(): {pipeboard_auth_manager.token_info.is_expired()}")
    else:
        print("No token returned from pipeboard_auth_manager")
    
    # 3. Check if the token is available through get_current_access_token
    print("\n--- Step 2: Check token via get_current_access_token ---")
    current_token = await get_current_access_token()
    
    if current_token:
        print(f"Token from get_current_access_token: {current_token[:10]}...{current_token[-5:]}")
        if current_token == pipeboard_token:
            print("✅ Tokens match: get_current_access_token returns the same token as pipeboard_auth_manager")
        else:
            print("❌ MISMATCH: get_current_access_token returns a different token!")
    else:
        print("No token returned from get_current_access_token")
    
    # 4. Check auth_manager directly
    print("\n--- Step 3: Check auth_manager directly ---")
    print(f"auth_manager object type: {type(auth_manager)}")
    print(f"auth_manager fields: {dir(auth_manager)}")
    
    try:
        auth_manager_token = auth_manager.get_access_token()
        if auth_manager_token:
            print(f"Token from auth_manager.get_access_token(): {auth_manager_token[:10]}...{auth_manager_token[-5:]}")
            if auth_manager_token == pipeboard_token:
                print("✅ Tokens match: auth_manager returns the same token as pipeboard_auth_manager")
            else:
                print("❌ MISMATCH: auth_manager returns a different token!")
        else:
            print("No token returned from auth_manager.get_access_token()")
    except AttributeError:
        print("auth_manager does not have get_access_token method")
    
    # 5. Check directly from wrapper function
    print("\n--- Step 4: Check token in wrapper function ---")
    
    # Create a simple wrapped function to log the token
    @meta_api_tool
    async def debug_token_wrapper(access_token=None, **kwargs):
        print(f"Inside wrapped function, access_token received: {access_token[:10]}...{access_token[-5:] if access_token else None}")
        return {"success": True, "token_present": access_token is not None}
    
    # Call the wrapped function directly without token
    print("Calling wrapped function without token parameter...")
    result = await debug_token_wrapper()
    print(f"Result from wrapper: {result}")
    
    # 6. Test get_ad_accounts with explicit token
    print("\n--- Step 5: Call get_ad_accounts with explicit token ---")
    try:
        # Call get_ad_accounts with explicit token
        ad_accounts_json = await get_ad_accounts(access_token=pipeboard_token)
        data = json.loads(ad_accounts_json)
        if isinstance(data, dict) and "error" in data:
            print(f"Error: {data['error']}")
        elif isinstance(data, list):
            print(f"Success! Found {len(data)} ad accounts.")
        else:
            print(f"Unexpected response format: {type(data)}")
    except Exception as e:
        print(f"Error calling get_ad_accounts with explicit token: {e}")
    
    # 7. Test get_ad_accounts without explicit token
    print("\n--- Step 6: Call get_ad_accounts without explicit token ---")
    try:
        # Call get_ad_accounts without explicit token
        ad_accounts_json = await get_ad_accounts()
        data = json.loads(ad_accounts_json)
        if isinstance(data, dict) and "error" in data:
            print(f"Error: {data['error']}")
            if "details" in data:
                print(f"Error details: {data['details']}")
        elif isinstance(data, list):
            print(f"Success! Found {len(data)} ad accounts.")
        else:
            print(f"Unexpected response format: {type(data)}")
    except Exception as e:
        print(f"Error calling get_ad_accounts without explicit token: {e}")
    
    # 8. Check global needs_authentication flag
    print(f"\nGlobal needs_authentication flag: {needs_authentication}")
    
    # 9. Check if original function is accessible
    print("\n--- Step 7: Check original function ---")
    if original_get_ad_accounts:
        print(f"Original get_ad_accounts function: {original_get_ad_accounts}")
        try:
            # Try to call the original function
            result = await original_get_ad_accounts(access_token=pipeboard_token)
            print(f"Original function result available: {result is not None}")
        except Exception as e:
            print(f"Error calling original function: {e}")
    else:
        print("Could not access original get_ad_accounts function")

if __name__ == "__main__":
    asyncio.run(debug_token_flow()) 