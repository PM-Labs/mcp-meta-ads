"""Insights and Reporting functionality for Meta Ads API."""

import json
from typing import Optional, Union, Dict
from .api import meta_api_tool, make_api_request
from .utils import download_image, try_multiple_download_methods, ad_creative_images, create_resource_from_image
from .server import mcp_server
import base64
import datetime


@mcp_server.tool()
@meta_api_tool
async def get_insights(access_token: str = None, object_id: str = None, 
                      time_range: Union[str, Dict[str, str]] = "maximum", breakdown: str = "", 
                      level: str = "ad") -> str:
    """
    Get performance insights for a campaign, ad set, ad or account.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        object_id: ID of the campaign, ad set, ad or account
        time_range: Either a preset time range string or a dictionary with "since" and "until" dates in YYYY-MM-DD format
                   Preset options: today, yesterday, this_month, last_month, this_quarter, maximum, data_maximum, 
                   last_3d, last_7d, last_14d, last_28d, last_30d, last_90d, last_week_mon_sun, 
                   last_week_sun_sat, last_quarter, last_year, this_week_mon_today, this_week_sun_today, this_year
                   Dictionary example: {"since":"2023-01-01","until":"2023-01-31"}
        breakdown: Optional breakdown dimension (e.g., age, gender, country)
        level: Level of aggregation (ad, adset, campaign, account)
    """
    if not object_id:
        return json.dumps({"error": "No object ID provided"}, indent=2)
        
    endpoint = f"{object_id}/insights"
    params = {
        "fields": "account_id,account_name,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,impressions,clicks,spend,cpc,cpm,ctr,reach,frequency,actions,conversions,unique_clicks,cost_per_action_type",
        "level": level
    }
    
    # Handle time range based on type
    if isinstance(time_range, dict):
        # Use custom date range with since/until parameters
        if "since" in time_range and "until" in time_range:
            params["time_range"] = json.dumps(time_range)
        else:
            return json.dumps({"error": "Custom time_range must contain both 'since' and 'until' keys in YYYY-MM-DD format"}, indent=2)
    else:
        # Use preset date range
        params["date_preset"] = time_range
    
    if breakdown:
        params["breakdowns"] = breakdown
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def debug_image_download(access_token: str = None, url: str = "", ad_id: str = "") -> str:
    """
    Debug image download issues and report detailed diagnostics.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        url: Direct image URL to test (optional)
        ad_id: Meta Ads ad ID (optional, used if url is not provided)
    """
    results = {
        "diagnostics": {
            "timestamp": str(datetime.datetime.now()),
            "methods_tried": [],
            "request_details": [],
            "network_info": {}
        }
    }
    
    # If no URL provided but ad_id is, get URL from ad creative
    if not url and ad_id:
        print(f"Getting image URL from ad creative for ad {ad_id}")
        # Get the creative details
        from .ads import get_ad_creatives
        creative_json = await get_ad_creatives(ad_id=ad_id, access_token=access_token)
        creative_data = json.loads(creative_json)
        results["creative_data"] = creative_data
        
        # Look for image URL in the creative
        if "full_image_url" in creative_data:
            url = creative_data.get("full_image_url")
        elif "thumbnail_url" in creative_data:
            url = creative_data.get("thumbnail_url")
    
    if not url:
        return json.dumps({
            "error": "No image URL provided or found in ad creative",
            "results": results
        }, indent=2)
    
    results["image_url"] = url
    
    # Try to get network information to help debug
    try:
        import socket
        from urllib.parse import urlparse
        hostname = urlparse(url).netloc
        ip_address = socket.gethostbyname(hostname)
        results["diagnostics"]["network_info"] = {
            "hostname": hostname,
            "ip_address": ip_address,
            "is_facebook_cdn": "fbcdn" in hostname
        }
    except Exception as e:
        results["diagnostics"]["network_info"] = {
            "error": str(e)
        }
    
    # Method 1: Basic download
    method_result = {
        "method": "Basic download with standard headers",
        "success": False
    }
    results["diagnostics"]["methods_tried"].append(method_result)
    
    try:
        headers = {
            "User-Agent": "curl/8.4.0"
        }
        import httpx
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            method_result["status_code"] = response.status_code
            method_result["headers"] = dict(response.headers)
            
            if response.status_code == 200:
                method_result["success"] = True
                method_result["content_length"] = len(response.content)
                method_result["content_type"] = response.headers.get("content-type")
                
                # Save this successful result
                results["image_data"] = {
                    "length": len(response.content),
                    "type": response.headers.get("content-type"),
                    "base64_sample": base64.b64encode(response.content[:100]).decode("utf-8") + "..." if response.content else None
                }
    except Exception as e:
        method_result["error"] = str(e)
    
    # Method 2: Browser emulation
    method_result = {
        "method": "Browser emulation with cookies",
        "success": False
    }
    results["diagnostics"]["methods_tried"].append(method_result)
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.facebook.com/",
            "Cookie": "presence=EDvF3EtimeF1697900316EuserFA21B00112233445566AA0EstateFDutF0CEchF_7bCC"
        }
        
        import httpx
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            method_result["status_code"] = response.status_code
            method_result["headers"] = dict(response.headers)
            
            if response.status_code == 200:
                method_result["success"] = True
                method_result["content_length"] = len(response.content)
                method_result["content_type"] = response.headers.get("content-type")
                
                # If first method didn't succeed, save this successful result
                if "image_data" not in results:
                    results["image_data"] = {
                        "length": len(response.content),
                        "type": response.headers.get("content-type"),
                        "base64_sample": base64.b64encode(response.content[:100]).decode("utf-8") + "..." if response.content else None
                    }
    except Exception as e:
        method_result["error"] = str(e)
    
    # Method 3: Graph API direct access (if applicable)
    if "fbcdn" in url or "facebook" in url:
        method_result = {
            "method": "Graph API direct access",
            "success": False
        }
        results["diagnostics"]["methods_tried"].append(method_result)
        
        try:
            # Try to reconstruct the attachment ID from URL if possible
            from urllib.parse import urlparse
            url_parts = urlparse(url).path.split("/")
            potential_ids = [part for part in url_parts if part.isdigit() and len(part) > 10]
            
            if potential_ids:
                attachment_id = potential_ids[0]
                endpoint = f"{attachment_id}?fields=url,width,height"
                api_result = await make_api_request(endpoint, access_token)
                
                method_result["api_response"] = api_result
                
                if "url" in api_result:
                    graph_url = api_result["url"]
                    method_result["graph_url"] = graph_url
                    
                    # Try to download from this Graph API URL
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(graph_url, timeout=30.0)
                        
                        method_result["status_code"] = response.status_code
                        if response.status_code == 200:
                            method_result["success"] = True
                            method_result["content_length"] = len(response.content)
                            
                            # If previous methods didn't succeed, save this successful result
                            if "image_data" not in results:
                                results["image_data"] = {
                                    "length": len(response.content),
                                    "type": response.headers.get("content-type"),
                                    "base64_sample": base64.b64encode(response.content[:100]).decode("utf-8") + "..." if response.content else None
                                }
        except Exception as e:
            method_result["error"] = str(e)
    
    # Generate a recommendation based on what we found
    if "image_data" in results:
        results["recommendation"] = "At least one download method succeeded. Consider implementing the successful method in the main code."
    else:
        # Check if the error appears to be access-related
        access_errors = False
        for method in results["diagnostics"]["methods_tried"]:
            if method.get("status_code") in [401, 403, 503]:
                access_errors = True
                
        if access_errors:
            results["recommendation"] = "Authentication or authorization errors detected. Images may require direct Facebook authentication not possible via API."
        else:
            results["recommendation"] = "Network or other technical errors detected. Check URL expiration or CDN restrictions."
    
    return json.dumps(results, indent=2)


@mcp_server.tool()
@meta_api_tool
async def save_ad_image_via_api(access_token: str = None, ad_id: str = None) -> str:
    """
    Try to save an ad image by using the Marketing API's attachment endpoints.
    This is an alternative approach when direct image download fails.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
        
    # First get the ad's creative ID
    endpoint = f"{ad_id}"
    params = {
        "fields": "creative,account_id"
    }
    
    ad_data = await make_api_request(endpoint, access_token, params)
    
    if "error" in ad_data:
        return json.dumps({
            "error": "Could not get ad data",
            "details": ad_data
        }, indent=2)
    
    if "creative" not in ad_data or "id" not in ad_data["creative"]:
        return json.dumps({
            "error": "No creative ID found for this ad",
            "ad_data": ad_data
        }, indent=2)
    
    creative_id = ad_data["creative"]["id"]
    account_id = ad_data.get("account_id", "")
    
    # Now get the creative object
    creative_endpoint = f"{creative_id}"
    creative_params = {
        "fields": "id,name,thumbnail_url,image_hash,asset_feed_spec"
    }
    
    creative_data = await make_api_request(creative_endpoint, access_token, creative_params)
    
    if "error" in creative_data:
        return json.dumps({
            "error": "Could not get creative data",
            "details": creative_data
        }, indent=2)
    
    # Approach 1: Try to get image through adimages endpoint if we have image_hash
    image_hash = None
    if "image_hash" in creative_data:
        image_hash = creative_data["image_hash"]
    elif "asset_feed_spec" in creative_data and "images" in creative_data["asset_feed_spec"] and len(creative_data["asset_feed_spec"]["images"]) > 0:
        image_hash = creative_data["asset_feed_spec"]["images"][0].get("hash")
    
    result = {
        "ad_id": ad_id,
        "creative_id": creative_id,
        "attempts": []
    }
    
    if image_hash and account_id:
        attempt = {
            "method": "adimages endpoint with hash",
            "success": False
        }
        result["attempts"].append(attempt)
        
        try:
            image_endpoint = f"act_{account_id}/adimages"
            image_params = {
                "hashes": [image_hash]
            }
            image_data = await make_api_request(image_endpoint, access_token, image_params)
            attempt["response"] = image_data
            
            if "data" in image_data and len(image_data["data"]) > 0 and "url" in image_data["data"][0]:
                url = image_data["data"][0]["url"]
                attempt["url"] = url
                
                # Try to download the image
                image_bytes = await download_image(url)
                if image_bytes:
                    attempt["success"] = True
                    attempt["image_size"] = len(image_bytes)
                    
                    # Save the image
                    resource_id = f"ad_creative_{ad_id}_method1"
                    resource_info = create_resource_from_image(
                        image_bytes, 
                        resource_id, 
                        f"Ad Creative for {ad_id} (Method 1)"
                    )
                    
                    # Return success with resource info
                    result.update(resource_info)
                    result["success"] = True
                    base64_sample = base64.b64encode(image_bytes[:100]).decode("utf-8") + "..."
                    result["base64_sample"] = base64_sample
        except Exception as e:
            attempt["error"] = str(e)
    
    # Approach 2: Try directly with the thumbnails endpoint
    attempt = {
        "method": "thumbnails endpoint on creative",
        "success": False
    }
    result["attempts"].append(attempt)
    
    try:
        thumbnails_endpoint = f"{creative_id}/thumbnails"
        thumbnails_params = {}
        thumbnails_data = await make_api_request(thumbnails_endpoint, access_token, thumbnails_params)
        attempt["response"] = thumbnails_data
        
        if "data" in thumbnails_data and len(thumbnails_data["data"]) > 0:
            for thumbnail in thumbnails_data["data"]:
                if "uri" in thumbnail:
                    url = thumbnail["uri"]
                    attempt["url"] = url
                    
                    # Try to download the image
                    image_bytes = await download_image(url)
                    if image_bytes:
                        attempt["success"] = True
                        attempt["image_size"] = len(image_bytes)
                        
                        # Save the image if method 1 didn't already succeed
                        if "success" not in result or not result["success"]:
                            resource_id = f"ad_creative_{ad_id}_method2"
                            resource_info = create_resource_from_image(
                                image_bytes, 
                                resource_id, 
                                f"Ad Creative for {ad_id} (Method 2)"
                            )
                            
                            # Return success with resource info
                            result.update(resource_info)
                            result["success"] = True
                            base64_sample = base64.b64encode(image_bytes[:100]).decode("utf-8") + "..."
                            result["base64_sample"] = base64_sample
                        
                        # No need to try more thumbnails if we succeeded
                        break
    except Exception as e:
        attempt["error"] = str(e)
    
    # Approach 3: Try using the preview shareable link as an alternate source
    attempt = {
        "method": "preview_shareable_link",
        "success": False
    }
    result["attempts"].append(attempt)
    
    try:
        # Get ad details with preview link
        ad_preview_endpoint = f"{ad_id}"
        ad_preview_params = {
            "fields": "preview_shareable_link"
        }
        ad_preview_data = await make_api_request(ad_preview_endpoint, access_token, ad_preview_params)
        
        if "preview_shareable_link" in ad_preview_data:
            preview_link = ad_preview_data["preview_shareable_link"]
            attempt["preview_link"] = preview_link
            
            # We can't directly download the preview image, but let's note it for manual inspection
            attempt["note"] = "Preview link available for manual inspection in browser"
    except Exception as e:
        attempt["error"] = str(e)
    
    # Overall result
    if "success" in result and result["success"]:
        result["message"] = "Successfully retrieved ad image through one of the API methods"
    else:
        result["message"] = "Failed to retrieve ad image through any API method"
        
    return json.dumps(result, indent=2) 