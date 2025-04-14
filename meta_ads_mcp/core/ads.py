"""Ad and Creative-related functionality for Meta Ads API."""

import json
from typing import Optional, Dict, Any
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
    
    endpoint = f"{account_id}/ads"
    params = {
        "fields": "id,name,adset_id,campaign_id,status,creative,created_time,updated_time,bid_amount,conversion_domain,tracking_specs",
        "limit": limit
    }
    
    if campaign_id:
        params["campaign_id"] = campaign_id
    
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
async def get_ad_creatives(access_token: str = None, ad_id: str = None) -> str:
    """
    Get creative details for a specific ad. Best if combined with get_ad_image to get the full image.
    
    Args:
        access_token: Meta API access token (optional - will use cached token if not provided)
        ad_id: Meta Ads ad ID
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
        
    # First, get the creative ID from the ad
    endpoint = f"{ad_id}"
    params = {
        "fields": "creative"
    }
    
    ad_data = await make_api_request(endpoint, access_token, params)
    
    if "error" in ad_data:
        return json.dumps(ad_data, indent=2)
    
    if "creative" not in ad_data:
        return json.dumps({"error": "No creative found for this ad"}, indent=2)
    
    creative_id = ad_data.get("creative", {}).get("id")
    if not creative_id:
        return json.dumps({"error": "Creative ID not found", "ad_data": ad_data}, indent=2)
    
    # Now get the creative details with essential fields
    creative_endpoint = f"{creative_id}"
    creative_params = {
        "fields": "id,name,title,body,image_url,object_story_spec,url_tags,link_url,thumbnail_url,image_hash,asset_feed_spec,object_type"
    }
    
    creative_data = await make_api_request(creative_endpoint, access_token, creative_params)
    
    # Try to get full-size images in different ways:
    
    # 1. First approach: Get ad images directly using the adimages endpoint
    if "image_hash" in creative_data:
        image_hash = creative_data.get("image_hash")
        image_endpoint = f"act_{ad_data.get('account_id', '')}/adimages"
        image_params = {
            "hashes": [image_hash]
        }
        image_data = await make_api_request(image_endpoint, access_token, image_params)
        if "data" in image_data and len(image_data["data"]) > 0:
            creative_data["full_image_url"] = image_data["data"][0].get("url")
    
    # 2. For creatives with object_story_spec
    if "object_story_spec" in creative_data:
        spec = creative_data.get("object_story_spec", {})
        
        # For link ads
        if "link_data" in spec:
            link_data = spec.get("link_data", {})
            # If there's an explicit image_url, use it
            if "image_url" in link_data:
                creative_data["full_image_url"] = link_data.get("image_url")
            # If there's an image_hash, try to get the full image
            elif "image_hash" in link_data:
                image_hash = link_data.get("image_hash")
                account_id = ad_data.get('account_id', '')
                if not account_id:
                    # Try to get account ID from ad ID
                    ad_details_endpoint = f"{ad_id}"
                    ad_details_params = {
                        "fields": "account_id"
                    }
                    ad_details = await make_api_request(ad_details_endpoint, access_token, ad_details_params)
                    account_id = ad_details.get('account_id', '')
                
                if account_id:
                    image_endpoint = f"act_{account_id}/adimages"
                    image_params = {
                        "hashes": [image_hash]
                    }
                    image_data = await make_api_request(image_endpoint, access_token, image_params)
                    if "data" in image_data and len(image_data["data"]) > 0:
                        creative_data["full_image_url"] = image_data["data"][0].get("url")
        
        # For photo ads
        if "photo_data" in spec:
            photo_data = spec.get("photo_data", {})
            if "image_hash" in photo_data:
                image_hash = photo_data.get("image_hash")
                account_id = ad_data.get('account_id', '')
                if not account_id:
                    # Try to get account ID from ad ID
                    ad_details_endpoint = f"{ad_id}"
                    ad_details_params = {
                        "fields": "account_id"
                    }
                    ad_details = await make_api_request(ad_details_endpoint, access_token, ad_details_params)
                    account_id = ad_details.get('account_id', '')
                
                if account_id:
                    image_endpoint = f"act_{account_id}/adimages"
                    image_params = {
                        "hashes": [image_hash]
                    }
                    image_data = await make_api_request(image_endpoint, access_token, image_params)
                    if "data" in image_data and len(image_data["data"]) > 0:
                        creative_data["full_image_url"] = image_data["data"][0].get("url")
    
    # 3. If there's an asset_feed_spec, try to get images from there
    if "asset_feed_spec" in creative_data and "images" in creative_data["asset_feed_spec"]:
        images = creative_data["asset_feed_spec"]["images"]
        if images and len(images) > 0 and "hash" in images[0]:
            image_hash = images[0]["hash"]
            account_id = ad_data.get('account_id', '')
            if not account_id:
                # Try to get account ID
                ad_details_endpoint = f"{ad_id}"
                ad_details_params = {
                    "fields": "account_id"
                }
                ad_details = await make_api_request(ad_details_endpoint, access_token, ad_details_params)
                account_id = ad_details.get('account_id', '')
            
            if account_id:
                image_endpoint = f"act_{account_id}/adimages"
                image_params = {
                    "hashes": [image_hash]
                }
                image_data = await make_api_request(image_endpoint, access_token, image_params)
                if "data" in image_data and len(image_data["data"]) > 0:
                    creative_data["full_image_url"] = image_data["data"][0].get("url")
    
    # If we have a thumbnail_url but no full_image_url, let's attempt to convert the thumbnail URL to full size
    if "thumbnail_url" in creative_data and "full_image_url" not in creative_data:
        thumbnail_url = creative_data["thumbnail_url"]
        # Try to convert the URL to get higher resolution by removing size parameters
        if "p64x64" in thumbnail_url:
            full_url = thumbnail_url.replace("p64x64", "p1080x1080")
            creative_data["full_image_url"] = full_url
        elif "dst-emg0" in thumbnail_url:
            # Remove the dst-emg0 parameter that seems to reduce size
            full_url = thumbnail_url.replace("dst-emg0_", "")
            creative_data["full_image_url"] = full_url
    
    # Fallback to using thumbnail or image_url if we still don't have a full image
    if "full_image_url" not in creative_data:
        if "thumbnail_url" in creative_data:
            creative_data["full_image_url"] = creative_data["thumbnail_url"]
        elif "image_url" in creative_data:
            creative_data["full_image_url"] = creative_data["image_url"]
    
    return json.dumps(creative_data, indent=2)


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
async def update_ad(ad_id: str, status: str = None, bid_amount: int = None, access_token: str = None) -> str:
    """
    Update an ad with new settings.
    
    Args:
        ad_id: Meta Ads ad ID
        status: Update ad status (ACTIVE, PAUSED, etc.)
        bid_amount: Bid amount in account currency (in cents for USD)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not ad_id:
        return json.dumps({"error": "No ad ID provided"}, indent=2)
    
    changes = {}
    
    if status is not None:
        changes['status'] = status
        
    if bid_amount is not None:
        changes['bid_amount'] = bid_amount
    
    if not changes:
        return json.dumps({"error": "No update parameters provided"}, indent=2)
    
    # Get current ad details for comparison
    current_details_json = await get_ad_details(ad_id=ad_id, access_token=access_token)
    current_details = json.loads(current_details_json)
    
    # Import the callback server components
    from .callback_server import start_callback_server, update_confirmation
    import urllib.parse
    
    # Start the callback server if not already running
    port = start_callback_server()
    
    # Generate confirmation URL with properly encoded parameters
    changes_json = json.dumps(changes)
    encoded_changes = urllib.parse.quote(changes_json)
    confirmation_url = f"http://localhost:{port}/confirm-update?ad_id={ad_id}&token={access_token}&changes={encoded_changes}"
    
    # Reset the update confirmation
    update_confirmation.clear()
    update_confirmation.update({"approved": False})
    
    # Return the confirmation link
    response = {
        "message": "Please confirm the ad update",
        "confirmation_url": confirmation_url,
        "markdown_link": f"[Click here to confirm ad update]({confirmation_url})",
        "current_details": current_details,
        "proposed_changes": changes,
        "instructions_for_llm": "You must present this link as clickable Markdown to the user using the markdown_link format provided.",
        "note": "After authenticating, the token will be automatically saved and your ad will be updated. Refresh the browser page if it doesn't load immediately."
    }
    
    return json.dumps(response, indent=2) 