"""Reach and frequency prediction functionality for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_reach_frequency_predictions(
    ad_account_id: str,
    limit: int = 10,
    access_token: Optional[str] = None
) -> str:
    """
    Get reach and frequency predictions for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of predictions to return (default: 10)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/reachfrequencypredictions"
    params = {
        "fields": "id,status,prediction_progress,curve_budget_reach",
        "limit": limit,
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_reach_frequency_prediction(
    ad_account_id: str,
    targeting: Dict[str, Any],
    start_time: str,
    end_time: str,
    frequency_cap: int,
    objective: str = "REACH",
    access_token: Optional[str] = None
) -> str:
    """
    Create a reach and frequency prediction for a campaign.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        targeting: Targeting spec dictionary (same format as ad set targeting).
                   Example: {"geo_locations": {"countries": ["AU"]}, "age_min": 18, "age_max": 65}
        start_time: Campaign start time as a Unix timestamp or ISO 8601 string
        end_time: Campaign end time as a Unix timestamp or ISO 8601 string
        frequency_cap: Maximum number of times an individual sees the ad over the campaign duration
        objective: Campaign objective for the prediction (default: 'REACH').
                   Options: REACH, BRAND_AWARENESS, etc.
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not targeting:
        return json.dumps({"error": "Targeting spec is required"}, indent=2)
    if not start_time:
        return json.dumps({"error": "start_time is required"}, indent=2)
    if not end_time:
        return json.dumps({"error": "end_time is required"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/reachfrequencypredictions"
    params: Dict[str, Any] = {
        "targeting_spec": json.dumps(targeting),
        "start_time": start_time,
        "end_time": end_time,
        "frequency_cap": frequency_cap,
        "objective": objective,
    }
    result = await make_api_request(endpoint, access_token, params, method="POST")
    return json.dumps(result, indent=2)
