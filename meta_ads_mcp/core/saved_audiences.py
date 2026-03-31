"""Saved audience management for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def create_saved_audience(
    ad_account_id: str,
    name: str,
    targeting: Dict[str, Any],
    access_token: Optional[str] = None,
) -> str:
    """
    Create a saved audience (targeting spec) for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Name for the saved audience
        targeting: Targeting spec dict (geo_locations, age_min, age_max, interests, etc.)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "No name provided"}, indent=2)
    if not targeting:
        return json.dumps({"error": "No targeting spec provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/saved_audiences"
    params: Dict[str, Any] = {
        "name": name,
        "targeting": json.dumps(targeting),
    }

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to create saved audience", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def update_saved_audience(
    audience_id: str,
    access_token: Optional[str] = None,
    name: str = "",
    targeting: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Update an existing saved audience.

    Args:
        audience_id: Saved audience ID
        access_token: Meta API access token (optional - will use cached token if not provided)
        name: New name for the audience (leave empty to keep current)
        targeting: Updated targeting spec dict (leave None to keep current)
    """
    if not audience_id:
        return json.dumps({"error": "No audience ID provided"}, indent=2)

    params: Dict[str, Any] = {}
    if name:
        params["name"] = name
    if targeting is not None:
        params["targeting"] = json.dumps(targeting)

    if not params:
        return json.dumps({"error": "No update parameters provided"}, indent=2)

    endpoint = f"{audience_id}"
    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to update saved audience", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def delete_saved_audience(
    audience_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Delete a saved audience.

    Args:
        audience_id: Saved audience ID to delete
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not audience_id:
        return json.dumps({"error": "No audience ID provided"}, indent=2)

    endpoint = f"{audience_id}"
    try:
        data = await make_api_request(endpoint, access_token, {}, method="DELETE")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to delete saved audience", "details": str(e)}, indent=2)
