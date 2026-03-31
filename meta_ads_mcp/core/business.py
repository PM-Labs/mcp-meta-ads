"""Business Manager functionality for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_business_info(
    business_id: str,
    access_token: Optional[str] = None
) -> str:
    """
    Get details about a Meta Business Manager.

    Args:
        business_id: Meta Business Manager ID
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not business_id:
        return json.dumps({"error": "No business ID provided"}, indent=2)

    endpoint = f"{business_id}"
    params = {
        "fields": "id,name,primary_page,created_time,update_time,verification_status",
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_business_ad_accounts(
    business_id: str,
    limit: int = 50,
    access_token: Optional[str] = None
) -> str:
    """
    Get ad accounts owned by a Meta Business Manager.

    Args:
        business_id: Meta Business Manager ID
        limit: Maximum number of ad accounts to return (default: 50)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not business_id:
        return json.dumps({"error": "No business ID provided"}, indent=2)

    endpoint = f"{business_id}/owned_ad_accounts"
    params = {
        "fields": "id,name,account_status,currency,amount_spent",
        "limit": limit,
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_business_users(
    business_id: str,
    limit: int = 50,
    access_token: Optional[str] = None
) -> str:
    """
    Get users who have access to a Meta Business Manager.

    Args:
        business_id: Meta Business Manager ID
        limit: Maximum number of users to return (default: 50)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not business_id:
        return json.dumps({"error": "No business ID provided"}, indent=2)

    endpoint = f"{business_id}/business_users"
    params = {
        "fields": "id,name,email,role",
        "limit": limit,
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)
