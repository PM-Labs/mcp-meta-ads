"""Product catalog functionality for Meta Ads API."""

import json
from typing import Optional, List, Dict, Any
from .api import meta_api_tool, make_api_request, ensure_act_prefix
from .server import mcp_server


@mcp_server.tool()
@meta_api_tool
async def get_product_catalogs(
    business_id: str,
    access_token: Optional[str] = None
) -> str:
    """
    Get product catalogs owned by a business.

    Args:
        business_id: Meta Business Manager ID
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not business_id:
        return json.dumps({"error": "No business ID provided"}, indent=2)

    endpoint = f"{business_id}/owned_product_catalogs"
    params = {
        "fields": "id,name,product_count,vertical",
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_catalog_products(
    catalog_id: str,
    limit: int = 25,
    filter: str = "",
    access_token: Optional[str] = None
) -> str:
    """
    Get products from a product catalog.

    Args:
        catalog_id: Product catalog ID
        limit: Maximum number of products to return (default: 25)
        filter: Optional filter string for product attributes
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not catalog_id:
        return json.dumps({"error": "No catalog ID provided"}, indent=2)

    endpoint = f"{catalog_id}/products"
    params: Dict[str, Any] = {
        "fields": "id,name,price,currency,availability,image_url,url,brand",
        "limit": limit,
    }
    if filter:
        params["filter"] = filter

    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def create_product_catalog(
    business_id: str,
    name: str,
    vertical: str = "commerce",
    access_token: Optional[str] = None
) -> str:
    """
    Create a new product catalog for a business.

    Args:
        business_id: Meta Business Manager ID
        name: Name of the product catalog
        vertical: Catalog vertical type (default: 'commerce'). Options: commerce, destinations,
                  flights, home_listings, hotels, vehicles
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not business_id:
        return json.dumps({"error": "No business ID provided"}, indent=2)
    if not name:
        return json.dumps({"error": "Name is required"}, indent=2)

    endpoint = f"{business_id}/owned_product_catalogs"
    params: Dict[str, Any] = {
        "name": name,
        "vertical": vertical,
    }
    result = await make_api_request(endpoint, access_token, params, method="POST")
    return json.dumps(result, indent=2)


@mcp_server.tool()
@meta_api_tool
async def get_product_sets(
    catalog_id: str,
    limit: int = 25,
    access_token: Optional[str] = None
) -> str:
    """
    Get product sets within a product catalog.

    Args:
        catalog_id: Product catalog ID
        limit: Maximum number of product sets to return (default: 25)
        access_token: Meta API access token (optional - will use cached token if not provided)
    """
    if not catalog_id:
        return json.dumps({"error": "No catalog ID provided"}, indent=2)

    endpoint = f"{catalog_id}/product_sets"
    params = {
        "fields": "id,name,product_count,filter",
        "limit": limit,
    }
    result = await make_api_request(endpoint, access_token, params)
    return json.dumps(result, indent=2)
