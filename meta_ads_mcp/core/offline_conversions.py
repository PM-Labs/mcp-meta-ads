"""Offline conversion event sets for Meta Ads API."""

import json
import hashlib
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


def _sha256(value: str) -> str:
    """Return SHA-256 hex digest of a normalised string."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


@mcp_server.tool()
@meta_api_tool
async def create_offline_event_set(
    ad_account_id: str,
    name: str,
    access_token: Optional[str] = None,
    description: str = "",
) -> str:
    """
    Create an offline conversion event set for a Meta Ads account.

    Args:
        ad_account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Name for the offline event set
        access_token: Meta API access token (optional - will use cached token if not provided)
        description: Optional description for the event set
    """
    if not ad_account_id:
        return json.dumps({"error": "No ad account ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "No name provided"}, indent=2)

    ad_account_id = ensure_act_prefix(ad_account_id)
    endpoint = f"{ad_account_id}/offline_conversion_data_sets"
    params: Dict[str, Any] = {"name": name}
    if description:
        params["description"] = description

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to create offline event set", "details": str(e)}, indent=2)


@mcp_server.tool()
@meta_api_tool
async def upload_offline_events(
    event_set_id: str,
    events: List[Dict[str, Any]],
    access_token: Optional[str] = None,
) -> str:
    """
    Upload offline conversion events to a Meta offline event set.

    Each event dict should contain:
        match_keys: dict with hashed PII fields (email, phone). Unhashed values will be
                    SHA-256 hashed automatically before upload.
        event_name: conversion event name (e.g., Purchase, Lead)
        event_time: Unix timestamp of the event
        value: Monetary value of the conversion (optional)
        currency: ISO 4217 currency code (e.g., USD) — required when value is set

    Args:
        event_set_id: Offline event set ID
        events: List of event dicts (see above)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not event_set_id:
        return json.dumps({"error": "No event set ID provided"}, indent=2)
    if not events:
        return json.dumps({"error": "No events provided"}, indent=2)

    # Hash any raw PII values in match_keys
    _pii_fields = {"email", "phone", "fn", "ln", "dob", "ct", "st", "zip", "country"}
    processed_events: List[Dict[str, Any]] = []
    for event in events:
        processed = dict(event)
        match_keys = processed.get("match_keys", {})
        hashed_keys: Dict[str, str] = {}
        for field, value in match_keys.items():
            if field.lower() in _pii_fields and isinstance(value, str) and len(value) != 64:
                # Value doesn't look pre-hashed — hash it
                hashed_keys[field] = _sha256(value)
            else:
                hashed_keys[field] = value
        processed["match_keys"] = hashed_keys
        processed_events.append(processed)

    endpoint = f"{event_set_id}/events"
    params: Dict[str, Any] = {
        "data": json.dumps(processed_events),
    }

    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({"error": "Failed to upload offline events", "details": str(e)}, indent=2)
