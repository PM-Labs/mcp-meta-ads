"""Automated rules management for Meta Ads API."""

import json
from typing import Optional, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def create_automated_rule(
    ad_account_id: str,
    name: str,
    evaluation_spec: Dict[str, Any],
    execution_spec: Dict[str, Any],
    access_token: Optional[str] = None,
    schedule_spec: Optional[Dict[str, Any]] = None,
    entity_type: str = "CAMPAIGN",
) -> str:
    """
    Create an automated rule for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Name of the automated rule
        evaluation_spec: Conditions that trigger the rule. Example:
                         {"evaluation_type": "SCHEDULE", "filters": [{"field": "spend", "value": 100, "operator": "GREATER_THAN"}]}
        execution_spec: Action to take when rule triggers. Example:
                        {"execution_type": "PAUSE"}
        access_token: Meta API access token (optional - will use cached token if not provided)
        schedule_spec: Optional schedule configuration. Example: {"schedule_type": "SEMI_HOURLY"}
        entity_type: Type of ad object the rule applies to — CAMPAIGN, ADSET, or AD (default: CAMPAIGN)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "No rule name provided"}, indent=2)
    if not evaluation_spec:
        return json.dumps({"error": "No evaluation spec provided"}, indent=2)
    if not execution_spec:
        return json.dumps({"error": "No execution spec provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/adrules_library"

    params: Dict[str, Any] = {
        "name": name,
        "evaluation_spec": json.dumps(evaluation_spec),
        "execution_spec": json.dumps(execution_spec),
        "entity_type": entity_type,
    }
    if schedule_spec:
        params["schedule_spec"] = json.dumps(schedule_spec)

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to create automated rule", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_automated_rules(
    ad_account_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get all automated rules for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/adrules_library"
    params = {
        "fields": "id,name,status,entity_type,evaluation_spec,execution_spec,schedule_spec,created_time,updated_time",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_rule_execution_history(
    rule_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get the execution history for an automated rule.

    Args:
        rule_id: Automated rule ID
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not rule_id:
        return json.dumps({"error": "No rule ID provided"}, indent=2)

    endpoint = f"{rule_id}/history"
    params = {
        "fields": "id,timestamp,is_manual,results,evaluation_spec,execution_spec",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)
