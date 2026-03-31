"""Advanced insights with breakdowns and async reports for Meta Ads API."""

import json
from typing import List, Optional, Dict, Any
from .api import meta_api_tool, make_api_request
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_insights_with_breakdowns(
    object_id: str,
    fields: List[str],
    access_token: Optional[str] = None,
    date_preset: str = "last_30d",
    time_range: Optional[Dict[str, str]] = None,
    time_increment: str = "1",
    breakdowns: Optional[List[str]] = None,
    level: str = "",
    filtering: Optional[List[Dict[str, Any]]] = None,
    limit: int = 100,
) -> str:
    """
    Get insights with demographic or placement breakdowns for a campaign, ad set, or ad.

    Args:
        object_id: Campaign, ad set, ad, or account ID to pull insights for
        fields: List of metrics/dimensions (e.g., ["impressions", "clicks", "spend", "ctr"])
        access_token: Meta API access token (optional - will use cached token if not provided)
        date_preset: Predefined date range (e.g., last_7d, last_30d, last_month, this_month)
        time_range: Custom date range dict with 'since' and 'until' in YYYY-MM-DD format
        time_increment: Aggregation period — "1" (daily), "7" (weekly), "monthly", or "all_days"
        breakdowns: List of breakdown dimensions (e.g., ["age", "gender"], ["device_platform"], ["publisher_platform"])
        level: Aggregation level — "campaign", "adset", "ad", or "account"
        filtering: List of filter objects (e.g., [{"field": "adset.delivery_info", "operator": "IN", "value": ["active"]}])
        limit: Maximum number of rows to return (default: 100)
    """
    if not object_id:
        return json.dumps({"error": "No object ID provided"}, indent=2)
    if not fields:
        return json.dumps({"error": "No fields provided"}, indent=2)

    endpoint = f"{object_id}/insights"
    params: Dict[str, Any] = {
        "fields": ",".join(fields),
        "limit": limit,
    }

    if time_range:
        params["time_range"] = json.dumps(time_range)
    else:
        params["date_preset"] = date_preset

    if time_increment:
        params["time_increment"] = time_increment
    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)
    if level:
        params["level"] = level
    if filtering:
        params["filtering"] = json.dumps(filtering)

    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_async_insights_report(
    object_id: str,
    fields: List[str],
    access_token: Optional[str] = None,
    date_preset: str = "last_30d",
    time_range: Optional[Dict[str, str]] = None,
    breakdowns: Optional[List[str]] = None,
    level: str = "",
) -> str:
    """
    Create an asynchronous insights report job for large data sets.

    Returns a report_run_id that can be polled with get_async_insights_report.

    Args:
        object_id: Campaign, ad set, ad, or account ID
        fields: List of metrics/dimensions to include in the report
        access_token: Meta API access token (optional - will use cached token if not provided)
        date_preset: Predefined date range (e.g., last_30d, last_month, last_year)
        time_range: Custom date range dict with 'since' and 'until' in YYYY-MM-DD format
        breakdowns: List of breakdown dimensions (e.g., ["age", "gender"])
        level: Aggregation level — "campaign", "adset", "ad", or "account"
    """
    if not object_id:
        return json.dumps({"error": "No object ID provided"}, indent=2)
    if not fields:
        return json.dumps({"error": "No fields provided"}, indent=2)

    endpoint = f"{object_id}/insights"
    params: Dict[str, Any] = {
        "fields": ",".join(fields),
    }

    if time_range:
        params["time_range"] = json.dumps(time_range)
    else:
        params["date_preset"] = date_preset

    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)
    if level:
        params["level"] = level

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to create async insights report", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_async_insights_report(
    report_run_id: str,
    access_token: Optional[str] = None,
    limit: int = 100,
    after: str = "",
) -> str:
    """
    Retrieve results from a completed async insights report job.

    First checks the report status; returns polling guidance if not yet complete.

    Args:
        report_run_id: The report run ID returned by create_async_insights_report
        access_token: Meta API access token (optional - will use cached token if not provided)
        limit: Maximum number of rows to return (default: 100)
        after: Pagination cursor for fetching subsequent pages
    """
    if not report_run_id:
        return json.dumps({"error": "No report run ID provided"}, indent=2)

    # Check status first
    status_data = await make_api_request(
        report_run_id,
        access_token,
        {"fields": "id,async_status,async_percent_completion"},
    )

    async_status = status_data.get("async_status", "")
    if async_status != "Job Completed":
        return json.dumps({
            "status": async_status,
            "percent_completion": status_data.get("async_percent_completion", 0),
            "message": "Report is not yet complete. Poll again later.",
            "report_run_id": report_run_id,
        }, indent=2)

    # Fetch results
    endpoint = f"{report_run_id}/insights"
    params: Dict[str, Any] = {"limit": limit}
    if after:
        params["after"] = after

    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)
