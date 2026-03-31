"""A/B testing (ad studies) functionality for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_ab_tests(
    ad_account_id: str,
    limit: int = 25,
    access_token: Optional[str] = None
) -> str:
    """
    Get A/B tests (ad studies) for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of studies to return (default: 25)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/adstudies"
    params = {
        "fields": "id,name,description,start_time,end_time,type,results",
        "limit": limit,
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_ab_test(
    ad_account_id: str,
    name: str,
    description: str = "",
    start_time: str = "",
    end_time: str = "",
    campaign_ids: Optional[List[str]] = None,
    access_token: Optional[str] = None
) -> str:
    """
    Create a new A/B test (ad study) for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Name of the A/B test
        description: Optional description of the test
        start_time: Start time in ISO 8601 format (e.g., '2024-01-01T00:00:00+0000')
        end_time: End time in ISO 8601 format
        campaign_ids: List of campaign IDs to include in the test
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "Name is required"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/adstudies"
    params: Dict[str, Any] = {
        "name": name,
        "type": "SPLIT_TEST",
    }
    if description:
        params["description"] = description
    if start_time:
        params["start_time"] = start_time
    if end_time:
        params["end_time"] = end_time
    if campaign_ids:
        params["cells"] = json.dumps([{"campaigns": campaign_ids}])

    result = await make_api_request(endpoint, access_token, params, method="POST")
    return json.dumps(result, indent=2)
