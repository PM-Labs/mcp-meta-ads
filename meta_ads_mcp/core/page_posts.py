"""Page posts management for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_page_posts(
    page_id: str,
    access_token: Optional[str] = None,
    limit: int = 25,
) -> str:
    """
    Get posts for a Facebook Page.

    Args:
        page_id: Facebook Page ID
        access_token: Meta API access token (optional - will use cached token if not provided)
        limit: Maximum number of posts to return (default: 25)
    """
    if not page_id:
        return json.dumps({"error": "No page ID provided"}, indent=2)

    endpoint = f"{page_id}/posts"
    params = {
        "fields": "id,message,created_time,type,permalink_url,shares,likes.summary(true),comments.summary(true)",
        "limit": limit,
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_post_insights(
    post_id: str,
    access_token: Optional[str] = None,
    metrics: Optional[List[str]] = None,
) -> str:
    """
    Get insights/metrics for a specific Facebook Page post.

    Args:
        post_id: Facebook post ID
        access_token: Meta API access token (optional - will use cached token if not provided)
        metrics: List of metric names to retrieve. Defaults to post_impressions, post_engaged_users,
                 post_clicks, post_reactions_by_type_total
    """
    if not post_id:
        return json.dumps({"error": "No post ID provided"}, indent=2)

    if metrics is None:
        metrics = [
            "post_impressions",
            "post_engaged_users",
            "post_clicks",
            "post_reactions_by_type_total",
        ]

    endpoint = f"{post_id}/insights"
    params = {
        "metric": ",".join(metrics),
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_promoted_post(
    ad_account_id: str,
    page_id: str,
    post_id: str,
    daily_budget: int,
    access_token: Optional[str] = None,
    targeting: Optional[Dict[str, Any]] = None,
    status: str = "PAUSED",
) -> str:
    """
    Create a campaign, ad set, and ad to promote an existing Facebook Page post.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        page_id: Facebook Page ID that owns the post
        post_id: ID of the existing page post to promote
        daily_budget: Daily budget in account currency (in cents, e.g. 1000 = $10.00)
        access_token: Meta API access token (optional - will use cached token if not provided)
        targeting: Targeting spec dict. Defaults to broad US targeting (18+) if not provided
        status: Campaign/adset/ad status — PAUSED or ACTIVE (default: PAUSED)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not page_id:
        return json.dumps({"error": "No page ID provided"}, indent=2)
    if not post_id:
        return json.dumps({"error": "No post ID provided"}, indent=2)
    if not daily_budget:
        return json.dumps({"error": "No daily budget provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)

    if targeting is None:
        targeting = {
            "geo_locations": {"countries": ["US"]},
            "age_min": 18,
        }

    # Step 1: Create campaign
    campaign_params: Dict[str, Any] = {
        "name": f"Promoted Post — {post_id}",
        "objective": "POST_ENGAGEMENT",
        "status": status,
        "special_ad_categories": json.dumps([]),
    }
    try:
        campaign_data = await make_api_request(
            f"{ad_account_id}/campaigns", access_token, campaign_params, method="POST"
        )
    except Exception as e:
        return json.dumps({"error": "Failed to create campaign", "details": str(e)}, indent=2)

    campaign_id = campaign_data.get("id")
    if not campaign_id:
        return json.dumps({"error": "Campaign creation returned no ID", "response": campaign_data}, indent=2)

    # Step 2: Create ad set
    adset_params: Dict[str, Any] = {
        "name": f"Promoted Post Adset — {post_id}",
        "campaign_id": campaign_id,
        "daily_budget": daily_budget,
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "POST_ENGAGEMENT",
        "targeting": json.dumps(targeting),
        "status": status,
    }
    try:
        adset_data = await make_api_request(
            f"{ad_account_id}/adsets", access_token, adset_params, method="POST"
        )
    except Exception as e:
        return json.dumps(
            {"error": "Campaign created but failed to create adset", "campaign_id": campaign_id, "details": str(e)},
            indent=2,
        )

    adset_id = adset_data.get("id")
    if not adset_id:
        return json.dumps(
            {"error": "Adset creation returned no ID", "campaign_id": campaign_id, "response": adset_data}, indent=2
        )

    # Step 3: Create ad using existing page post
    ad_params: Dict[str, Any] = {
        "name": f"Promoted Post Ad — {post_id}",
        "adset_id": adset_id,
        "creative": json.dumps({
            "object_story_id": f"{page_id}_{post_id}",
        }),
        "status": status,
    }
    try:
        ad_data = await make_api_request(
            f"{ad_account_id}/ads", access_token, ad_params, method="POST"
        )
    except Exception as e:
        return json.dumps(
            {
                "error": "Campaign and adset created but failed to create ad",
                "campaign_id": campaign_id,
                "adset_id": adset_id,
                "details": str(e),
            },
            indent=2,
        )

    return json.dumps(
        {
            "success": True,
            "campaign_id": campaign_id,
            "adset_id": adset_id,
            "ad_id": ad_data.get("id"),
            "status": status,
        },
        indent=2,
    )
