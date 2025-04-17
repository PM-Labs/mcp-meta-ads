"""Ad and Creative-related functionality for Meta Ads API."""

import json
from typing import Optional, Dict, Any, List
import io
from PIL import Image as PILImage
from mcp.server.fastmcp import Image

from .api import meta_api_tool, make_api_request
from .accounts import get_ad_accounts
from .utils import download_image, try_multiple_download_methods, ad_creative_images
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_ads(access_token: str = None, account_id: str = None, limit: int = 10, 
                 campaign_id: str = "", adset_id: str = "") -> str:
    """
    Get ads for a Meta Ads account with optional filtering.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        limit: Maximum number of ads to return (default: 10)
        campaign_id: Optional campaign ID to filter by
        adset_id: Optional ad set ID to filter by
    """
    # If no account ID is specified, try to get the first one for the user
    if not account_id:
        accounts_json = await get_ad_accounts("me", json.dumps({"limit": 1}), access_token)
        accounts_data = json.loads(accounts_json)
        
        if "data" in accounts_data and accounts_data["data"]:
            account_id = accounts_data["data"][0]["id"]
        else:
            return json.dumps({"error": "No account ID specified and no accounts found for user"}, indent=2)
    
    # Use campaign-specific endpoint if campaign_id is provided
    if campaign_id:
        endpoint = f"{campaign_id}/ads"
        params = {
            "fields": "id,name,adset_id,campaign_id,status,creative,created_time,updated_time,bid_amount,conversion_domain,tracking_specs",
            "limit": limit
        }
        # Adset ID can still be used to filter within the campaign
        if adset_id:
            params["adset_id"] = adset_id
    else:
        # Default to account-level endpoint if no campaign_id
        endpoint = f"{account_id}/ads"
        params = {
            "fields": "id,name,adset_id,campaign_id,status,creative,created_time,updated_time,bid_amount,conversion_domain,tracking_specs",
            "limit": limit
        }
        # Adset ID can filter at the account level if no campaign specified
        if adset_id:
            params["adset_id"] = adset_id

    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_ad_details(access_token: str = None, ad_id: str = None) -> str:
    """
    Get detailed information about a specific ad.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
        
    endpoint = f"{ad_id}"
    params = {
        "fields": "id,name,adset_id,campaign_id,status,creative,created_time,updated_time,bid_amount,conversion_domain,tracking_specs,preview_shareable_link"
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_ad(
    account_id: str = None,
    name: str = None,
    adset_id: str = None,
    creative_id: str = None,
    status: str = "PAUSED",
    bid_amount = None,
    tracking_specs: Optional[List[Dict[str, Any]]] = None,
    access_token: str = None
) -> str:
    """
    Create a new ad with an existing creative.
    
    Args:
        account_id: Meta Ads account ID (format: act_XXXXXXXXX)
        name: Ad name
        adset_id: Ad set ID where this ad will be placed
        creative_id: ID of an existing creative to use
        status: Initial ad status (default: PAUSED)
        bid_amount: Optional bid amount in account currency (in cents)
        tracking_specs: Optional tracking specifications (e.g., for pixel events).
                      Example: [{"action.type":"offsite_conversion","fb_pixel":["YOUR_PIXEL_ID"]}]
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    # Check required parameters
    if not account_id:
        return json.dumps({"error": "No account ID provided"}, indent=2)
    
    if not name:
        return json.dumps({"error": "No ad name provided"}, indent=2)
    
    if not adset_id:
        return json.dumps({"error": "No ad set ID provided"}, indent=2)
    
    if not creative_id:
        return json.dumps({"error": "No creative ID provided"}, indent=2)
    
    endpoint = f"{account_id}/ads"
    
    params = {
        "name": name,
        "adset_id": adset_id,
        "creative": {"creative_id": creative_id},
        "status": status
    }
    
    # Add bid amount if provided
    if bid_amount is not None:
        params["bid_amount"] = str(bid_amount)
        
    # Add tracking specs if provided
    if tracking_specs is not None:
        params["tracking_specs"] = json.dumps(tracking_specs) # Needs to be JSON encoded string
    
    try:
        data = await make_api_request(endpoint, access_token, params, method="POST")
        return json.dumps(data, indent=2)
    except Exception as e:
        error_msg = str(e)
        return json.dumps({
            "error": "Failed to create ad",
            "details": error_msg,
            "params_sent": params
        }, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_ad_creatives(access_token: str = None, ad_id: str = None) -> str:
    """
    Get creative details for a specific ad. Best if combined with get_ad_image to get the full image.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
        
    endpoint = f"{ad_id}/adcreatives"
    params = {
        "fields": "id,name,status,thumbnail_url,image_url,image_hash,object_story_spec" # Added image_hash
    }
    
    data = await make_api_request(endpoint, access_token, params)
    
    # Add image URLs for direct viewing if available
    if 'data' in data:
        for creative in data['data']:
            creative['image_urls_for_viewing'] = ad_creative_images(creative)

    return json.dumps(data, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_ad_image(access_token: str = None, ad_id: str = None) -> Image:
    """
    Get, download, and visualize a Meta ad image in one step. Useful to see the image in the LLM.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    
    Returns:
        The ad image ready for direct visual analysis
    """
    if not ad_id:
        return "Error: No ad ID provided"
        
    print(f"Attempting to get and analyze creative image for ad {ad_id}")
    
    # First, get creative and account IDs
    ad_endpoint = f"{ad_id}"
    ad_params = {
        "fields": "creative{id},account_id"
    }
    
    ad_data = await make_api_request(ad_endpoint, access_token, ad_params)
    
    if "error" in ad_data:
        return f"Error: Could not get ad data - {json.dumps(ad_data)}"
    
    # Extract account_id
    account_id = ad_data.get("account_id", "")
    if not account_id:
        return "Error: No account ID found"
    
    # Extract creative ID
    if "creative" not in ad_data:
        return "Error: No creative found for this ad"
        
    creative_data = ad_data.get("creative", {})
    creative_id = creative_data.get("id")
    if not creative_id:
        return "Error: No creative ID found"
    
    # Get creative details to find image hash
    creative_endpoint = f"{creative_id}"
    creative_params = {
        "fields": "id,name,image_hash,asset_feed_spec"
    }
    
    creative_details = await make_api_request(creative_endpoint, access_token, creative_params)
    
    # Identify image hashes to use from creative
    image_hashes = []
    
    # Check for direct image_hash on creative
    if "image_hash" in creative_details:
        image_hashes.append(creative_details["image_hash"])
    
    # Check asset_feed_spec for image hashes - common in Advantage+ ads
    if "asset_feed_spec" in creative_details and "images" in creative_details["asset_feed_spec"]:
        for image in creative_details["asset_feed_spec"]["images"]:
            if "hash" in image:
                image_hashes.append(image["hash"])
    
    if not image_hashes:
        # If no hashes found, try to extract from the first creative we found in the API
        # Get creative for ad to try to extract hash
        creative_json = await get_ad_creatives(ad_id, "", access_token)
        creative_data = json.loads(creative_json)
        
        # Try to extract hash from asset_feed_spec
        if "asset_feed_spec" in creative_data and "images" in creative_data["asset_feed_spec"]:
            images = creative_data["asset_feed_spec"]["images"]
            if images and len(images) > 0 and "hash" in images[0]:
                image_hashes.append(images[0]["hash"])
    
    if not image_hashes:
        return "Error: No image hashes found in creative"
    
    print(f"Found image hashes: {image_hashes}")
    
    # Now fetch image data using adimages endpoint with specific format
    image_endpoint = f"act_{account_id}/adimages"
    
    # Format the hashes parameter exactly as in our successful curl test
    hashes_str = f'["{image_hashes[0]}"]'  # Format first hash only, as JSON string array
    
    image_params = {
        "fields": "hash,url,width,height,name,status",
        "hashes": hashes_str
    }
    
    print(f"Requesting image data with params: {image_params}")
    image_data = await make_api_request(image_endpoint, access_token, image_params)
    
    if "error" in image_data:
        return f"Error: Failed to get image data - {json.dumps(image_data)}"
    
    if "data" not in image_data or not image_data["data"]:
        return "Error: No image data returned from API"
    
    # Get the first image URL
    first_image = image_data["data"][0]
    image_url = first_image.get("url")
    
    if not image_url:
        return "Error: No valid image URL found"
    
    print(f"Downloading image from URL: {image_url}")
    
    # Download the image
    image_bytes = await download_image(image_url)
    
    if not image_bytes:
        return "Error: Failed to download image"
    
    try:
        # Convert bytes to PIL Image
        img = PILImage.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        # Create a byte stream of the image data
        byte_arr = io.BytesIO()
        img.save(byte_arr, format="JPEG")
        img_bytes = byte_arr.getvalue()
        
        # Return as an Image object that LLM can directly analyze
        return Image(data=img_bytes, format="jpeg")
        
    except Exception as e:
        return f"Error processing image: {str(e)}"


@mcp_server.tool()
@meta_api_tool
async def update_ad(
    ad_id: str,
    status: str = None,
    bid_amount: int = None,
    tracking_specs = None,
    access_token: str = None
) -> str:
    """
    Update an ad with new settings.
    
    Args:
        ad_id: Meta Ads ad ID
        status: Update ad status (ACTIVE, PAUSED, etc.)
        bid_amount: Bid amount in account currency (in cents for USD)
        tracking_specs: Optional tracking specifications (e.g., for pixel events).
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_id:
        return json.dumps({"error": "Ad ID is required"}, indent=2)

    params = {}
    if status:
        params["status"] = status
    if bid_amount is not None:
        # Ensure bid_amount is sent as a string if it's not null
        params["bid_amount"] = str(bid_amount)
    if tracking_specs is not None: # Add tracking_specs to params if provided
        params["tracking_specs"] = json.dumps(tracking_specs) # Needs to be JSON encoded string

    if not params:
        return json.dumps({"error": "No update parameters provided (status, bid_amount, or tracking_specs)"}, indent=2)

    endpoint = f"{ad_id}"
    data = await make_api_request(endpoint, access_token, params, method='POST')

    return json.dumps(data, indent=2)