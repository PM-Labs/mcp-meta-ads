"""Duplication functionality for Meta Ads API."""

import json
import os
import httpx
from typing import Optional, Dict, Any, List, Union
from .server import mcp_server
from .api import meta_api_tool


# Only register the duplication functions if the environment variable is set
ENABLE_DUPLICATION = bool(os.environ.get("META_ADS_ENABLE_DUPLICATION", ""))

if ENABLE_DUPLICATION:
    @mcp_server.tool()
    @meta_api_tool
    async def duplicate_campaign(
        campaign_id: str,
        access_token: str = None,
        name_suffix: Optional[str] = " - Copy",
        include_ad_sets: bool = True,
        include_ads: bool = True,
        include_creatives: bool = True,
        copy_schedule: bool = False,
        new_daily_budget: Optional[float] = None,
        new_status: Optional[str] = "PAUSED"
    ) -> str:
        """
        Duplicate a Meta Ads campaign with all its ad sets and ads.

        **This is a premium feature available with Pipeboard Pro.**
        
        Args:
            campaign_id: Meta Ads campaign ID to duplicate
            name_suffix: Suffix to add to the duplicated campaign name
            include_ad_sets: Whether to duplicate ad sets within the campaign
            include_ads: Whether to duplicate ads within ad sets
            include_creatives: Whether to duplicate ad creatives
            copy_schedule: Whether to copy the campaign schedule
            new_daily_budget: Override the daily budget for the new campaign
            new_status: Status for the new campaign (ACTIVE or PAUSED)
        """
        return await _forward_duplication_request(
            "campaign",
            campaign_id,
            access_token,
            {
                "name_suffix": name_suffix,
                "include_ad_sets": include_ad_sets,
                "include_ads": include_ads,
                "include_creatives": include_creatives,
                "copy_schedule": copy_schedule,
                "new_daily_budget": new_daily_budget,
                "new_status": new_status
            }
        )

    @mcp_server.tool()
    @meta_api_tool
    async def duplicate_adset(
        adset_id: str,
        access_token: str = None,
        target_campaign_id: Optional[str] = None,
        name_suffix: Optional[str] = " - Copy",
        include_ads: bool = True,
        include_creatives: bool = True,
        new_daily_budget: Optional[float] = None,
        new_status: Optional[str] = "PAUSED"
    ) -> str:
        """
        Duplicate a Meta Ads ad set with its ads.

        **This is a premium feature available with Pipeboard Pro.**
        
        Args:
            adset_id: Meta Ads ad set ID to duplicate
            target_campaign_id: Campaign ID to move the duplicated ad set to (optional)
            name_suffix: Suffix to add to the duplicated ad set name
            include_ads: Whether to duplicate ads within the ad set
            include_creatives: Whether to duplicate ad creatives
            new_daily_budget: Override the daily budget for the new ad set
            new_status: Status for the new ad set (ACTIVE or PAUSED)
        """
        return await _forward_duplication_request(
            "adset",
            adset_id,
            access_token,
            {
                "target_campaign_id": target_campaign_id,
                "name_suffix": name_suffix,
                "include_ads": include_ads,
                "include_creatives": include_creatives,
                "new_daily_budget": new_daily_budget,
                "new_status": new_status
            }
        )

    @mcp_server.tool()
    @meta_api_tool
    async def duplicate_ad(
        ad_id: str,
        access_token: str = None,
        target_adset_id: Optional[str] = None,
        name_suffix: Optional[str] = " - Copy",
        duplicate_creative: bool = True,
        new_creative_name: Optional[str] = None,
        new_status: Optional[str] = "PAUSED"
    ) -> str:
        """
        Duplicate a Meta Ads ad.

        **This is a premium feature available with Pipeboard Pro.**
        
        Args:
            ad_id: Meta Ads ad ID to duplicate
            target_adset_id: Ad set ID to move the duplicated ad to (optional)
            name_suffix: Suffix to add to the duplicated ad name
            duplicate_creative: Whether to duplicate the ad creative
            new_creative_name: Override name for the duplicated creative
            new_status: Status for the new ad (ACTIVE or PAUSED)
        """
        return await _forward_duplication_request(
            "ad",
            ad_id,
            access_token,
            {
                "target_adset_id": target_adset_id,
                "name_suffix": name_suffix,
                "duplicate_creative": duplicate_creative,
                "new_creative_name": new_creative_name,
                "new_status": new_status
            }
        )

    @mcp_server.tool()
    @meta_api_tool
    async def duplicate_creative(
        creative_id: str,
        access_token: str = None,
        name_suffix: Optional[str] = " - Copy",
        new_primary_text: Optional[str] = None,
        new_headline: Optional[str] = None,
        new_description: Optional[str] = None,
        new_cta_type: Optional[str] = None,
        new_destination_url: Optional[str] = None
    ) -> str:
        """
        Duplicate a Meta Ads creative.

        **This is a premium feature available with Pipeboard Pro.**
        
        Args:
            creative_id: Meta Ads creative ID to duplicate
            name_suffix: Suffix to add to the duplicated creative name
            new_primary_text: Override the primary text for the new creative
            new_headline: Override the headline for the new creative
            new_description: Override the description for the new creative
            new_cta_type: Override the call-to-action type for the new creative
            new_destination_url: Override the destination URL for the new creative
        """
        return await _forward_duplication_request(
            "creative",
            creative_id,
            access_token,
            {
                "name_suffix": name_suffix,
                "new_primary_text": new_primary_text,
                "new_headline": new_headline,
                "new_description": new_description,
                "new_cta_type": new_cta_type,
                "new_destination_url": new_destination_url
            }
        )


async def _forward_duplication_request(resource_type: str, resource_id: str, access_token: str, options: Dict[str, Any]) -> str:
    """
    Forward duplication request to the cloud-hosted MCP API.
    
    Args:
        resource_type: Type of resource to duplicate (campaign, adset, ad, creative)
        resource_id: ID of the resource to duplicate
        access_token: Meta API access token from the request
        options: Duplication options
    """
    try:
        if not access_token:
            return json.dumps({
                "error": "authentication_required",
                "message": "Meta Ads access token not found",
                "details": {
                    "required": "Valid access token from authenticated session"
                }
            }, indent=2)

        # Construct the API endpoint
        base_url = "https://mcp.pipeboard.co"
        endpoint = f"{base_url}/api/meta/duplicate/{resource_type}/{resource_id}"
        
        # Prepare the request
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "meta-ads-mcp/1.0"
        }
        
        # Remove None values from options
        clean_options = {k: v for k, v in options.items() if v is not None}
        
        # Make the request to the cloud service
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=clean_options
            )
            
            if response.status_code == 200:
                result = response.json()
                return json.dumps(result, indent=2)
            elif response.status_code == 403:
                # Premium feature upgrade message
                return json.dumps({
                    "error": "premium_feature_required",
                    "message": f"Professional {resource_type} duplication is a premium feature",
                    "details": {
                        "feature": f"Meta Ads {resource_type.title()} Duplication",
                        "description": f"Duplicate {resource_type}s with advanced options and bulk operations",
                        "benefits": [
                            "Preserve all targeting and optimization settings",
                            "Bulk duplication across campaigns",
                            "Advanced naming and organization options",
                            "Cross-account duplication support",
                            "Performance-based automatic duplication",
                            "Template system for reusable patterns",
                            "Compliance validation (DSA, youth targeting)",
                            "White-label client reporting"
                        ],
                        "upgrade_url": "https://pipeboard.co/upgrade",
                        "contact_email": "info@pipeboard.co",
                        "early_access": "Contact us for early access and special pricing"
                    },
                    "request_parameters": {
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        **clean_options
                    },
                    "preview": {
                        "would_duplicate": {
                            "resource_type": resource_type,
                            "resource_id": resource_id,
                            "new_name": f"Original Name{options.get('name_suffix', ' - Copy')}",
                            "status": options.get('new_status', 'PAUSED')
                        },
                        "estimated_components": _get_estimated_components(resource_type, options),
                        "supported_features": [
                            "Name customization",
                            "Budget modification", 
                            "Status control",
                            "Cross-campaign/adset movement",
                            "Creative text modifications",
                            "Schedule preservation",
                            "Targeting duplication",
                            "Performance tracking"
                        ]
                    }
                }, indent=2)
            elif response.status_code == 401:
                return json.dumps({
                    "error": "authentication_failed",
                    "message": "Invalid or expired access token",
                    "details": {
                        "suggestion": "Please reconnect your Meta Ads account",
                        "status_code": response.status_code
                    }
                }, indent=2)
            elif response.status_code == 429:
                return json.dumps({
                    "error": "rate_limit_exceeded", 
                    "message": "Meta API rate limit exceeded",
                    "details": {
                        "suggestion": "Please wait before retrying",
                        "retry_after": response.headers.get("Retry-After", "60")
                    }
                }, indent=2)
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("message", error_detail)
                except:
                    pass
                
                return json.dumps({
                    "error": "duplication_failed",
                    "message": f"Failed to duplicate {resource_type}",
                    "details": {
                        "status_code": response.status_code,
                        "error_detail": error_detail,
                        "resource_type": resource_type,
                        "resource_id": resource_id
                    }
                }, indent=2)
    
    except httpx.TimeoutException:
        return json.dumps({
            "error": "request_timeout",
            "message": "Request to duplication service timed out",
            "details": {
                "suggestion": "Please try again later",
                "timeout": "30 seconds"
            }
        }, indent=2)
    
    except httpx.RequestError as e:
        return json.dumps({
            "error": "network_error", 
            "message": "Failed to connect to duplication service",
            "details": {
                "error": str(e),
                "suggestion": "Check your internet connection and try again"
            }
        }, indent=2)
    
    except Exception as e:
        return json.dumps({
            "error": "unexpected_error",
            "message": f"Unexpected error during {resource_type} duplication",
            "details": {
                "error": str(e),
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        }, indent=2)


def _get_estimated_components(resource_type: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Get estimated components that would be duplicated."""
    if resource_type == "campaign":
        components = {"campaigns": 1}
        if options.get("include_ad_sets", True):
            components["ad_sets"] = "3-5 (estimated)"
        if options.get("include_ads", True):
            components["ads"] = "5-15 (estimated)"
        if options.get("include_creatives", True):
            components["creatives"] = "5-15 (estimated)"
        return components
    elif resource_type == "adset":
        components = {"ad_sets": 1}
        if options.get("include_ads", True):
            components["ads"] = "2-5 (estimated)"
        if options.get("include_creatives", True):
            components["creatives"] = "2-5 (estimated)"
        return components
    elif resource_type == "ad":
        components = {"ads": 1}
        if options.get("duplicate_creative", True):
            components["creatives"] = 1
        return components
    elif resource_type == "creative":
        return {"creatives": 1}
    
    return {} 