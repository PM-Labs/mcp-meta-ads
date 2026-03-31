"""Advanced ad creative operations for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def delete_ad_creative(
    creative_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Delete an ad creative.

    Args:
        creative_id: Ad creative ID to delete
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not creative_id:
        return json.dumps({"error": "No creative ID provided"}, indent=2)

    endpoint = f"{creative_id}"
    try:
        data = await make_api_request(endpoint, access_token, {}, method="DELETE")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to delete ad creative", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_creative_preview(
    creative_id: str,
    access_token: Optional[str] = None,
    ad_format: str = "DESKTOP_FEED_STANDARD",
) -> str:
    """
    Get an HTML preview of an ad creative.

    Args:
        creative_id: Ad creative ID
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_format: Ad format for the preview (default: DESKTOP_FEED_STANDARD).
                   Other common values: MOBILE_FEED_STANDARD, INSTAGRAM_STANDARD,
                   RIGHT_COLUMN_STANDARD, DESKTOP_FEED_SQUARE
    """
    if not creative_id:
        return json.dumps({"error": "No creative ID provided"}, indent=2)

    endpoint = f"{creative_id}/previews"
    params = {
        "ad_format": ad_format,
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_dynamic_creative_elements(
    adset_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get the ad creatives and their dynamic elements for a given ad set.

    Returns asset_feed_spec and object_story_spec which describe the individual
    creative components used in dynamic creative optimisation.

    Args:
        adset_id: Ad set ID
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not adset_id:
        return json.dumps({"error": "No adset ID provided"}, indent=2)

    endpoint = f"{adset_id}/adcreatives"
    params = {
        "fields": "id,name,asset_feed_spec,object_story_spec",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)
