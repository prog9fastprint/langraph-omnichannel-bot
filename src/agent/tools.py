from langchain_core.tools import tool
from src.services.erp_client import erp_client
import json

@tool
async def search_products(filter: str) -> str:
    """
    Searches for products and checks their real-time stock levels in the ERP.
    Input should be a search query (filter) matching product name or SKU.
    Returns a JSON string containing a list of products with their stock, price, category, etc.
    """
    try:
        response = await erp_client.get("inventory/api/ai/products/", params={"filter": filter})
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e), "message": f"Could not search products for {filter}"})

@tool
async def check_order_status(order_id: str) -> str:
    """
    Checks the status of a specific order in the ERP.
    Input should be the order ID as a string.
    Returns a JSON string containing order status and details.
    """
    try:
        response = await erp_client.get(f"/api/erp/orders/{order_id}/status/")
        return json.dumps(response)
    except Exception as e:
        return json.dumps({"error": str(e), "message": f"Could not retrieve status for order {order_id}"})

@tool
async def get_product_price(product_id: str):
    """Call this when user asks about the price, cost, or discount of a FastPrint raw material or accessory."""
    product = await erp_client.get_product_by_id(product_id)
    return f"The price for {product['name']} is {product['price']}."

@tool
async def get_product_stock(product_id: str):
    """Call this when user asks about availability, stock levels, or inventory for FastPrint products."""
    product = await erp_client.get_product_by_id(product_id)
    return f"{product['name']} has {product['stock']} units currently in stock."
