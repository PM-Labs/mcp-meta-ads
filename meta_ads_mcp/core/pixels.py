"""Meta Pixel (dataset) management for Meta Ads API."""

import json
from typing import Optional
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_pixels(
    ad_account_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get all Meta Pixels (datasets) associated with a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/adspixels"
    params = {
        "fields": "id,name,code,creation_time,last_fired_time,is_unavailable",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_pixel_events(
    pixel_id: str,
    access_token: Optional[str] = None,
    start_time: str = "",
    end_time: str = "",
) -> str:
    """
    Get event statistics for a Meta Pixel.

    Args:
        pixel_id: Meta Pixel / Dataset ID
        access_token: Meta API access token (optional - will use cached token if not provided)
        start_time: Start of the time range as a Unix timestamp string (optional)
        end_time: End of the time range as a Unix timestamp string (optional)
    """
    if not pixel_id:
        return json.dumps({"error": "No pixel ID provided"}, indent=2)

    endpoint = f"{pixel_id}/stats"
    params: dict = {}
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time

    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)
