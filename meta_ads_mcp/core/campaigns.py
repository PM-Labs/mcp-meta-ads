"""Campaign-related functionality for Meta Ads API."""

import json
from typing import List, Optional, Dict, Any, Union
from .api import meta_api_tool, make_api_request
from .accounts import get_ad_accounts
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_campaigns(access_token: str = None, account_id: str = None, limit: int = 10, status_filter: str = "") -> str:
    """
    Get campaigns for a Meta Ads account with optional filtering.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of campaigns to return (default: 10)
        status_filter: Filter by status (empty for all, or 'ACTIVE', 'PAUSED', etc.)
    """
    # If no account ID is specified, try to get the first one for the user
    if not account_id:
        accounts_json = await get_ad_accounts("me", json.dumps({"limit": 1}), access_token)
        accounts_data = json.loads(accounts_json)
        
        if "data" in accounts_data and accounts_data["data"]:
            account_id = accounts_data["data"][0]["id"]
        else:
            return json.dumps({"error": "No account ID specified and no accounts found for user"}, indent=2)
    
    endpoint = f"{account_id}/campaigns"
    params = {
        "fields": "id,name,objective,status,daily_budget,lifetime_budget,buying_type,start_time,stop_time,created_time,updated_time,bid_strategy",
        "limit": limit
    }
    
    if status_filter:
        params["effective_status"] = [status_filter]
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_campaign_details(access_token: str = None, campaign_id: str = None) -> str:
    """
    Get detailed information about a specific campaign.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        campaign_id: Meta Ads campaign ID
    """
    if not campaign_id:
        return json.dumps({"error": "No campaign ID provided"}, indent=2)
    
    endpoint = f"{campaign_id}"
    params = {
        "fields": "id,name,objective,status,daily_budget,lifetime_budget,buying_type,start_time,stop_time,created_time,updated_time,bid_strategy,special_ad_categories,special_ad_category_country,budget_remaining,configured_status"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_campaign(
    access_token: str = None,
    account_id: str = None,
    name: str = None,
    objective: str = None,
    status: str = "PAUSED",
    special_ad_categories: List[str] = None,
    daily_budget: Optional[int] = None,
    lifetime_budget: Optional[int] = None,
    buying_type: str = None,
    bid_strategy: str = None,
    bid_cap: Optional[int] = None,
    spend_cap: Optional[int] = None,
    campaign_budget_optimization: bool = None,
    ab_test_control_setups: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Create a new campaign in a Meta Ads account.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Campaign name
        objective: Campaign objective (AWARENESS, TRAFFIC, ENGAGEMENT, etc.)
        status: Initial campaign status (default: PAUSED)
        special_ad_categories: List of special ad categories if applicable
        daily_budget: Daily budget in account currency (in cents)
        lifetime_budget: Lifetime budget in account currency (in cents)
        buying_type: Buying type (e.g., 'AUCTION')
        bid_strategy: Bid strategy (e.g., 'LOWEST_COST', 'LOWEST_COST_WITH_BID_CAP', 'COST_CAP')
        bid_cap: Bid cap in account currency (in cents)
        spend_cap: Spending limit for the campaign in account currency (in cents)
        campaign_budget_optimization: Whether to enable campaign budget optimization
        ab_test_control_setups: Settings for A/B testing (e.g., [{"name":"Creative A", "ad_format":"SINGLE_IMAGE"}])
    """
    # Check required parameters
    if not account_id:
        return json.dumps({"error": "No account ID provided"}, indent=2)
    
    if not name:
        return json.dumps({"error": "No campaign name provided"}, indent=2)
        
    if not objective:
        return json.dumps({"error": "No campaign objective provided"}, indent=2)
    
    endpoint = f"{account_id}/campaigns"
    
    params = {
        "name": name,
        "objective": objective,
        "status": status,
    }
    
    if special_ad_categories:
        params["special_ad_categories"] = special_ad_categories
    
    if daily_budget:
        params["daily_budget"] = daily_budget
    
    if lifetime_budget:
        params["lifetime_budget"] = lifetime_budget
    
    # Add new parameters
    if buying_type:
        params["buying_type"] = buying_type
    
    if bid_strategy:
        params["bid_strategy"] = bid_strategy
    
    if bid_cap:
        params["bid_cap"] = bid_cap
    
    if spend_cap:
        params["spend_cap"] = spend_cap
    
    if campaign_budget_optimization is not None:
        params["campaign_budget_optimization"] = campaign_budget_optimization
    
    if ab_test_control_setups:
        params["ab_test_control_setups"] = json.dumps(ab_test_control_setups)
    
    data = await make_api_request(endpoint, access_token, params, method="POST")
    
    return json.dumps(data, indent=2) 