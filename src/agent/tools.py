import httpx
import json
from langchain_core.tools import tool
from src.services.erp_client import erp_client

@tool
async def search_products(query: str) -> str:
    """
    Searches for FastPrint products semantically based on descriptions, tags, and titles.
    Input should be a natural language search query (e.g., "Kertas HVS A4" or "tinta printer").
    Returns a JSON string containing a list of matching products with their SKU, title, body description, and tags.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Call the local FastAPI semantic search endpoint
            response = await client.get("http://localhost:8000/api/product/search", params={"query": query}, timeout=10.0)
            response.raise_for_status()
            return json.dumps(response.json())
    except Exception as e:
        return json.dumps({"error": str(e), "message": f"Could not perform semantic search for query '{query}'"})

@tool
async def check_order_status(so_number: str) -> str:
    """
    Checks the status of a specific order in the ERP (Sales Order or Marketplace Order).
    Input should be the order number or tracking invoice number as a string (e.g., "SO/2026/..." or AWB/marketplace invoice number).
    Returns a JSON string containing order status, tracking number, expedition carrier, and creation time.
    """
    try:
        response = await erp_client.get("inventory/api/ai/order-status/", params={"so_number": so_number})
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e), "message": f"Could not retrieve status for order '{so_number}'"})

@tool
async def get_available_pricelists() -> str:
    """
    Retrieves a list of all available pricelists.
    Use this tool when a user asks for a product price without specifying a pricelist,
    so you can present the available options to them.
    Returns a JSON string containing the list of available pricelists.
    """
    try:
        response = await erp_client.get("inventory/api/ai/pricelists/")
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e), "message": "Could not retrieve available pricelists"})

@tool
async def get_pricelist_detail(product_sku: str, pricelist_id: str) -> str:
    """
    Retrieves the price information for a specific product based on a specific pricelist.
    Input should be the product's variant SKU and the pricelist ID.
    Returns a JSON string with the product's price details from the specified pricelist.
    """
    try:
        response = await erp_client.get("inventory/api/ai/pricelist-detail/", params={"sku": product_sku, "pricelist_id": pricelist_id})
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e), "message": f"Could not retrieve price details for SKU '{product_sku}' in pricelist '{pricelist_id}'"})

@tool
async def get_product_stock(product_sku: str) -> str:
    """
    Retrieves the real-time stock availability for a specific product variant in the ERP.
    Input should be the product's variant SKU (e.g., SKU code from search results).
    Returns a JSON string with the product's stock quantity.
    """
    try:
        response = await erp_client.get("inventory/api/ai/stock/", params={"sku": product_sku})
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e), "message": f"Could not retrieve stock details for SKU '{product_sku}'"})
