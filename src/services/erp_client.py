import hashlib
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import httpx
from src.config import settings

logger = logging.getLogger(__name__)

class ERPClient:
    def __init__(self):
        self.base_url = settings.ERP_BASE_URL
        self._token: str | None = None  # In-memory token cache       
        # httpx Client for general authenticated requests
        self._client = httpx.AsyncClient(base_url=self.base_url)
        self._lock = asyncio.Lock()

    def _generate_md5_header(self) -> str:
        """
        Generates the dynamic MD5 hash required for the auth endpoint.
        Format: MD5("erp_master_nexus-{YYYY-MM-DD-HH:MM}")
        Note: Using UTC time. If the ERP server is in a different timezone, 
        this might need adjustment.
        """
        wib = timezone(timedelta(hours=7))
        now = datetime.now(wib)
        time_str = now.strftime("%Y-%m-%d-%H:%M")
        raw_string = f"erp_master_nexus-{time_str}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    async def _get_valid_token(self) -> str:
        """
        Checks the in-memory cache for a token. If it doesn't exist,
        fetches a new one from the ERP using the provided credentials.
        """
        async with self._lock:
            if self._token:
                return self._token
                
            logger.info("Fetching new ERP authentication token...")
            
            auth_url = f"{self.base_url}/external_api/get_token/"
            payload = {
                "username": settings.ERP_USERNAME,
                "password": settings.ERP_PASSWORD
            }
            
            headers = {
                "key": self._generate_md5_header(),
                "Content-Type": "application/json"
            }
            
            try:
                # We use a temporary async client just for the auth request since it needs specific headers
                async with httpx.AsyncClient() as client:
                    response = await client.post(auth_url, json=payload, headers=headers, timeout=10.0)
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    self._token = data.get("access") or data.get("token") or data.get("access_token")
                    
                    if not self._token:
                         raise ValueError("Token not found in ERP response")
                         
                    logger.info("Successfully retrieved and cached ERP token.")
                    return self._token
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"ERP Auth HTTP error {e.response.status_code}: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Failed to fetch ERP token: {e}")
                raise

    async def _request(self, method: str, endpoint: str, **kwargs):
        """Helper method to make authenticated requests to the ERP API."""
        
        # Ensure we have a valid token before making the request
        token = await self._get_valid_token()
        
        # Prepare headers for this specific request
        headers = kwargs.get("headers", {}).copy()
        headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        kwargs["headers"] = headers
        
        try:
            response = await self._client.request(method, endpoint, **kwargs)
            
            # If token expired (401), we might want to clear cache and retry here in the future
            if response.status_code == 401:
                logger.warning("ERP returned 401 Unauthorized. Clearing token cache.")
                async with self._lock:
                    self._token = None
                
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {method} {endpoint}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {method} {endpoint}: {e}")
            raise

    async def get_product_by_id(self, product_id: str) -> dict:
        """Fetches product details from the list endpoint and filters by product_id."""
        products = await self.get("inventory/api/ai/products/")
        if not isinstance(products, list):
             logger.error(f"Expected list of products, got {type(products)}: {products}")
             raise ValueError("Unexpected API response format.")

        for product in products:
            if isinstance(product, dict) and str(product.get("id")) == str(product_id):
                return product
        raise ValueError(f"Product {product_id} not found.")

    async def get_product_by_sku(self, sku: str) -> dict | None:
        """Fetches live product details from the ERP using the SKU as a query parameter."""
        try:
            response = await self.get("inventory/api/ai/products/", params={"sku": sku})
            
            # The API might return a list of matches or a single object.
            if isinstance(response, list) and len(response) > 0:
                return response[0]
            elif isinstance(response, dict) and response.get("sku") == sku:
                return response
            elif isinstance(response, dict) and "data" in response:
                if isinstance(response["data"], list) and len(response["data"]) > 0:
                    return response["data"][0]
                    
            logger.warning(f"Product with SKU {sku} not found or unexpected format in ERP.")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch product by SKU {sku}: {e}")
            return None

    async def get(self, endpoint: str, params: dict = None):
        """Makes an authenticated GET request to the ERP API."""
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, json_data: dict = None):
        """Makes an authenticated POST request to the ERP API."""
        return await self._request("POST", endpoint, json=json_data)

# Singleton instance
erp_client = ERPClient()
