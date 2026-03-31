"""Attribution reporting for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_attribution_report(
    ad_account_id: str,
    access_token: Optional[str] = None,
    date_preset: str = "last_30d",
    attribution_windows: Optional[List[str]] = None,
) -> str:
    """
    Get an attribution report for a Meta Ads account, broken down by attribution window.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        access_token: Meta API access token (optional - will use cached token if not provided)
        date_preset: Date range preset (default: last_30d). Options: today, yesterday, last_7d,
                     last_30d, last_90d, this_month, last_month, this_year
        attribution_windows: List of attribution windows to include. Defaults to
                             ["1d_click", "7d_click", "1d_view"]
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    if attribution_windows is None:
        attribution_windows = ["1d_click", "7d_click", "1d_view"]

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/insights"
    params: Dict[str, Any] = {
        "fields": "campaign_name,adset_name,ad_name,impressions,clicks,spend,actions,action_values",
        "date_preset": date_preset,
        "action_attribution_windows": json.dumps(attribution_windows),
        "level": "ad",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_attribution_settings(
    ad_account_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get the attribution settings for a Meta Ads account.

    Returns attribution_spec, default_dsa_beneficiary, and default_dsa_payor fields.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}"
    params: Dict[str, Any] = {
        "fields": "attribution_spec,default_dsa_beneficiary,default_dsa_payor",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)
