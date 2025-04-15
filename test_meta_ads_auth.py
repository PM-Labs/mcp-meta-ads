#!/usr/bin/env python3
"""
Test script for Meta Ads MCP authentication flow.
This script shows how to authenticate with the Meta Ads API and run a simple command.
"""

import asyncio
import argparse
import json
import os

# Import the auth manager from our Meta Ads MCP module
from meta_ads_mcp.core.auth import auth_manager
from meta_ads_mcp.core.accounts import get_ad_accounts

async def test_authentication(app_id=None, force_login=False):
    """Test the authentication flow and run a simple command"""
    print("===== Meta Ads MCP Authentication Test =====")
    
    # Update app ID if provided
    if app_id:
        auth_manager.app_id = app_id
    else:
        # If no app ID is provided and META_APP_ID is the default, look for it in environment
        if auth_manager.app_id == "YOUR_CLIENT_ID":
            env_app_id = os.environ.get("META_APP_ID")
            if env_app_id:
                print(f"Using Meta App ID from environment: {env_app_id}")
                auth_manager.app_id = env_app_id
            else:
                print("Warning: No Meta App ID provided. Please set META_APP_ID environment variable or use --app-id")
    
    # Force authentication if requested
    if force_login:
        print("Forcing new authentication...")
        auth_manager.authenticate(force_refresh=True)
    else:
        print("Getting access token (using cached token if available)...")
        token = auth_manager.get_access_token()
        if token:
            # Mask token for display
            masked_token = token[:10] + "..." + token[-5:]
            print(f"Access token obtained: {masked_token}")
        else:
            print("No token available. Authentication may be required.")
    
    # Test the API by getting ad accounts - not explicitly passing the token
    # The @meta_api_tool decorator will handle authentication implicitly
    print("\nFetching ad accounts to test API connectivity...")
    ad_accounts_json = await get_ad_accounts()
    
    # Check if ad_accounts_json is already a dictionary or a JSON string
    if isinstance(ad_accounts_json, dict):
        ad_accounts = ad_accounts_json
    else:
        ad_accounts = json.loads(ad_accounts_json)
    
    if "error" in ad_accounts:
        print(f"Error fetching ad accounts: {ad_accounts['error']}")
    else:
        # Display accounts in a nice format
        print("\nAd Accounts:")
        if "data" in ad_accounts and ad_accounts["data"]:
            for i, account in enumerate(ad_accounts["data"], 1):
                print(f"  {i}. {account.get('name', 'Unnamed')} (ID: {account.get('id', 'Unknown')})")
        else:
            print("  No ad accounts found.")
    
    print("\n===== Test Complete =====")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Meta Ads MCP authentication")
    parser.add_argument("--app-id", type=str, help="Meta App ID (Client ID) for authentication")
    parser.add_argument("--force-login", action="store_true", help="Force new login even if cached token exists")
    
    args = parser.parse_args()
    
    asyncio.run(test_authentication(app_id=args.app_id, force_login=args.force_login)) 