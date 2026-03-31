"""Custom audience management for Meta Ads API."""

import json
import hashlib
from typing import List, Optional, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def create_custom_audience(
    ad_account_id: str,
    name: str,
    subtype: str,
    access_token: Optional[str] = None,
    description: str = "",
    customer_file_source: str = "",
    rule: Optional[Dict[str, Any]] = None,
    retention_days: int = 0,
) -> str:
    """
    Create a new custom audience for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Name of the custom audience
        subtype: Audience subtype (e.g., CUSTOM, WEBSITE, APP, OFFLINE_CONVERSION, LOOKALIKE, ENGAGEMENT, etc.)
        access_token: Meta API access token (optional - will use cached token if not provided)
        description: Optional description of the audience
        customer_file_source: Source of customer data (e.g., USER_PROVIDED_ONLY, PARTNER_PROVIDED_ONLY)
        rule: JSON rule object for WEBSITE or engagement audiences
        retention_days: Number of days to retain users (0 = no expiry)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "No audience name provided"}, indent=2)
    if not subtype:
        return json.dumps({"error": "No subtype provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/customaudiences"

    params: Dict[str, Any] = {
        "name": name,
        "subtype": subtype,
    }
    if description:
        params["description"] = description
    if customer_file_source:
        params["customer_file_source"] = customer_file_source
    if rule is not None:
        params["rule"] = json.dumps(rule)
    if retention_days:
        params["retention_days"] = retention_days

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to create custom audience", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_custom_audiences(
    ad_account_id: str,
    access_token: Optional[str] = None,
    limit: int = 25,
) -> str:
    """
    Get custom audiences for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        access_token: Meta API access token (optional - will use cached token if not provided)
        limit: Maximum number of audiences to return (default: 25)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/customaudiences"
    params = {
        "fields": "id,name,subtype,description,approximate_count,delivery_status,operation_status,time_created,time_updated,retention_days",
        "limit": limit,
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def update_custom_audience(
    audience_id: str,
    access_token: Optional[str] = None,
    name: str = "",
    description: str = "",
    rule: Optional[Dict[str, Any]] = None,
    retention_days: int = 0,
) -> str:
    """
    Update an existing custom audience.

    Args:
        audience_id: Custom audience ID
        access_token: Meta API access token (optional - will use cached token if not provided)
        name: New name for the audience
        description: New description for the audience
        rule: Updated rule object for WEBSITE or engagement audiences
        retention_days: Updated retention period in days
    """
    if not audience_id:
        return json.dumps({"error": "No audience ID provided"}, indent=2)

    endpoint = f"{audience_id}"
    params: Dict[str, Any] = {}

    if name:
        params["name"] = name
    if description:
        params["description"] = description
    if rule is not None:
        params["rule"] = json.dumps(rule)
    if retention_days:
        params["retention_days"] = retention_days

    if not params:
        return json.dumps({"error": "No update parameters provided"}, indent=2)

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to update custom audience", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def delete_custom_audience(
    audience_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Delete a custom audience.

    Args:
        audience_id: Custom audience ID to delete
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not audience_id:
        return json.dumps({"error": "No audience ID provided"}, indent=2)

    endpoint = f"{audience_id}"
    try:
        data = await make_api_request(endpoint, access_token, {}, method="DELETE")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to delete custom audience", "details": str(e)}, indent=2)


def _sha256_hash(value: str) -> str:
    """Return SHA-256 hex digest of a string."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


# PII fields that should be hashed before sending to Meta
_PII_FIELDS = {"email", "phone", "fn", "ln", "dob", "gen", "doby", "age", "ct", "st", "zip", "country", "madid"}


@mcp_server.tool()
@meta_api_tool
async def add_users_to_custom_audience(
    audience_id: str,
    schema: List[str],
    data: List[List[str]],
    access_token: Optional[str] = None,
    is_raw: bool = False,
) -> str:
    """
    Add users to an existing custom audience.

    Args:
        audience_id: Custom audience ID
        schema: List of field names (e.g., ["EMAIL", "FN", "LN"])
        data: List of user records, each matching the schema order
        access_token: Meta API access token (optional - will use cached token if not provided)
        is_raw: If True, SHA-256 hash all PII fields before sending (required for raw data)
    """
    if not audience_id:
        return json.dumps({"error": "No audience ID provided"}, indent=2)
    if not schema or not data:
        return json.dumps({"error": "Schema and data are required"}, indent=2)

    # Hash PII fields when is_raw=True
    processed_data = data
    if is_raw:
        processed_data = []
        schema_lower = [s.lower() for s in schema]
        for row in data:
            hashed_row = []
            for i, value in enumerate(row):
                field = schema_lower[i] if i < len(schema_lower) else ""
                if field in _PII_FIELDS and value:
                    hashed_row.append(_sha256_hash(value))
                else:
                    hashed_row.append(value)
            processed_data.append(hashed_row)

    endpoint = f"{audience_id}/users"
    payload = {
        "payload": json.dumps({
            "schema": schema,
            "data": processed_data,
        })
    }

    try:
        result = await make_api_request(endpoint, access_token, payload, method="POST")
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to add users to custom audience", "details": str(e)}, indent=2)
