"""Lookalike audience management for Meta Ads API."""

import json
from typing import Optional
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def create_lookalike_audience(
    ad_account_id: str,
    name: str,
    origin_audience_id: str,
    access_token: Optional[str] = None,
    country: str = "AU",
    ratio: float = 0.01,
    type: str = "similarity",
) -> str:
    """
    Create a lookalike audience based on an existing custom audience.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Name of the lookalike audience
        origin_audience_id: ID of the source custom audience to base the lookalike on
        access_token: Meta API access token (optional - will use cached token if not provided)
        country: Two-letter country code for the lookalike audience (default: AU)
        ratio: Size of the lookalike audience as a fraction of country population (0.01 to 0.20)
        type: Lookalike type — 'similarity' (closer match) or 'reach' (larger audience)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "No audience name provided"}, indent=2)
    if not origin_audience_id:
        return json.dumps({"error": "No origin audience ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/customaudiences"

    lookalike_spec = {
        "origin": [{"id": origin_audience_id, "type": "CUSTOM_AUDIENCE"}],
        "country": country,
        "ratio": ratio,
        "type": type,
    }

    params = {
        "name": name,
        "subtype": "LOOKALIKE",
        "lookalike_spec": json.dumps(lookalike_spec),
    }

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to create lookalike audience", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_lookalike_audience_status(
    audience_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get the current status and details of a lookalike audience.

    Args:
        audience_id: Lookalike audience ID
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not audience_id:
        return json.dumps({"error": "No audience ID provided"}, indent=2)

    endpoint = f"{audience_id}"
    params = {
        "fields": "id,name,subtype,approximate_count,delivery_status,operation_status,lookalike_spec,time_created,time_updated",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)
