"""Conversions API (CAPI) and custom conversions for Meta Ads API."""

import json
import hashlib
from typing import List, Optional, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server

# PII fields in user_data that must be SHA-256 hashed
_CAPI_PII_FIELDS = {"em", "ph", "fn", "ln", "ct", "st", "zp", "country", "external_id", "ge", "db"}


def _sha256(value: str) -> str:
    """Return SHA-256 hex digest of a stripped, lowercased string."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _looks_hashed(value: str) -> bool:
    """Return True if value appears to already be a SHA-256 hex digest."""
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _hash_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Hash PII fields in a user_data dict if not already hashed."""
    hashed = {}
    for key, value in user_data.items():
        if key in _CAPI_PII_FIELDS and isinstance(value, str) and value and not _looks_hashed(value):
            hashed[key] = _sha256(value)
        else:
            hashed[key] = value
    return hashed


@mcp_server.tool()
@meta_api_tool
async def send_conversion_events(
    pixel_id: str,
    events: List[Dict[str, Any]],
    access_token: Optional[str] = None,
    test_event_code: str = "",
) -> str:
    """
    Send server-side conversion events via Meta Conversions API (CAPI).

    PII fields in user_data (em, ph, fn, ln, ct, st, zp, country, ge, db, external_id)
    will be automatically SHA-256 hashed if not already hashed.

    Args:
        pixel_id: Meta Pixel / Dataset ID
        events: List of event objects. Each event should include:
                - event_name (e.g., "Purchase", "Lead", "PageView")
                - event_time (Unix timestamp)
                - user_data (dict with identifiers: em, ph, fn, ln, etc.)
                - custom_data (optional dict with value, currency, content_ids, etc.)
                - event_source_url (optional)
                - action_source (e.g., "website", "email", "app", "phone_call")
        access_token: Meta API access token (optional - will use cached token if not provided)
        test_event_code: Test event code from Events Manager to verify events without real tracking
    """
    if not pixel_id:
        return json.dumps({"error": "No pixel ID provided"}, indent=2)
    if not events:
        return json.dumps({"error": "No events provided"}, indent=2)

    # Hash PII in user_data for each event
    processed_events = []
    for event in events:
        processed_event = dict(event)
        if "user_data" in processed_event and isinstance(processed_event["user_data"], dict):
            processed_event["user_data"] = _hash_user_data(processed_event["user_data"])
        processed_events.append(processed_event)

    endpoint = f"{pixel_id}/events"
    params: Dict[str, Any] = {
        "data": json.dumps(processed_events),
    }
    if test_event_code:
        params["test_event_code"] = test_event_code

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to send conversion events", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_capi_diagnostics(
    pixel_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get Conversions API diagnostics for a pixel to check event quality and deduplication.

    Args:
        pixel_id: Meta Pixel / Dataset ID
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not pixel_id:
        return json.dumps({"error": "No pixel ID provided"}, indent=2)

    endpoint = f"{pixel_id}/server_events_diagnostic"
    params = {
        "fields": "diagnostics",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_custom_conversion(
    ad_account_id: str,
    name: str,
    event_source_id: str,
    rule: str,
    access_token: Optional[str] = None,
    custom_event_type: str = "",
    default_conversion_value: float = 0,
) -> str:
    """
    Create a custom conversion for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Name for the custom conversion
        event_source_id: Pixel ID or app ID that fires the events
        rule: JSON string defining the URL or event rule (e.g., '{"url": {"i_contains": "thank-you"}}')
        access_token: Meta API access token (optional - will use cached token if not provided)
        custom_event_type: Optional event type (e.g., PURCHASE, LEAD, COMPLETE_REGISTRATION)
        default_conversion_value: Default monetary value assigned to each conversion
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "No conversion name provided"}, indent=2)
    if not event_source_id:
        return json.dumps({"error": "No event source ID provided"}, indent=2)
    if not rule:
        return json.dumps({"error": "No rule provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/customconversions"

    params: Dict[str, Any] = {
        "name": name,
        "event_source_id": event_source_id,
        "rule": rule,
    }
    if custom_event_type:
        params["custom_event_type"] = custom_event_type
    if default_conversion_value:
        params["default_conversion_value"] = default_conversion_value

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to create custom conversion", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_custom_conversions(
    ad_account_id: str,
    access_token: Optional[str] = None,
) -> str:
    """
    Get all custom conversions for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/customconversions"
    params = {
        "fields": "id,name,rule,event_source_id,custom_event_type,default_conversion_value,creation_time,last_fired_time,is_archived",
    }
    data = await make_api_request(endpoint, access_token, params)
    return json.dumps(data, indent=2)
