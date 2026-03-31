"""Lead form functionality for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_lead_forms(
    page_id: str,
    limit: int = 25,
    access_token: Optional[str] = None
) -> str:
    """
    Get lead generation forms for a Facebook Page.

    Args:
        page_id: Facebook Page ID
        limit: Maximum number of forms to return (default: 25)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not page_id:
        return json.dumps({"error": "No page ID provided"}, indent=2)

    endpoint = f"{page_id}/leadgen_forms"
    params = {
        "fields": "id,name,status,created_time,leads_count",
        "limit": limit,
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_leads(
    form_id: str,
    limit: int = 100,
    access_token: Optional[str] = None
) -> str:
    """
    Get leads collected by a lead generation form.

    Args:
        form_id: Lead generation form ID
        limit: Maximum number of leads to return (default: 100)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not form_id:
        return json.dumps({"error": "No form ID provided"}, indent=2)

    endpoint = f"{form_id}/leads"
    params = {
        "fields": "id,created_time,field_data",
        "limit": limit,
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_lead_form(
    page_id: str,
    name: str,
    questions: List[Dict[str, Any]],
    privacy_policy_url: str,
    thank_you_page_url: str = "",
    access_token: Optional[str] = None
) -> str:
    """
    Create a new lead generation form for a Facebook Page.

    Args:
        page_id: Facebook Page ID
        name: Name of the lead form
        questions: List of question objects. Each question should have a 'type' field
                   (e.g., 'EMAIL', 'FULL_NAME', 'PHONE', 'CUSTOM') and optionally a
                   'label' for custom questions.
                   Example: [{"type": "EMAIL"}, {"type": "FULL_NAME"},
                              {"type": "CUSTOM", "label": "What is your budget?"}]
        privacy_policy_url: URL to your privacy policy (required by Meta)
        thank_you_page_url: Optional URL to redirect users after form submission
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not page_id:
        return json.dumps({"error": "No page ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "Name is required"}, indent=2)
    if not questions:
        return json.dumps({"error": "At least one question is required"}, indent=2)
    if not privacy_policy_url:
        return json.dumps({"error": "Privacy policy URL is required"}, indent=2)

    endpoint = f"{page_id}/leadgen_forms"
    params: Dict[str, Any] = {
        "name": name,
        "questions": json.dumps(questions),
        "privacy_policy": json.dumps({"url": privacy_policy_url}),
    }
    if thank_you_page_url:
        params["thank_you_page"] = json.dumps({"body": "Thank you!", "website_url": thank_you_page_url})

    result = await make_api_request(endpoint, access_token, params, method="POST")
    return json.dumps(result, indent=2)
