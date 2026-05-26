import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from src.services.erp_client import erp_client
from src.config import settings

# Force override for testing
settings.ERP_BASE_URL = "https://erp.fastprint.id"
settings.ERP_USERNAME = "super@erp"
settings.ERP_PASSWORD = "super"

erp_client.base_url = settings.ERP_BASE_URL
erp_client._client.base_url = settings.ERP_BASE_URL

def _generate_wib_md5_header() -> str:
    # WIB is UTC+7
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib)
    time_str = now.strftime("%Y-%m-%d-%H:%M")
    raw_string = f"erp_master_nexus-{time_str}"
    print(f"DEBUG: raw_string = {raw_string}")
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

# Monkey-patch the method for testing
erp_client._generate_md5_header = _generate_wib_md5_header

async def main():
    print(f"Testing ERP Client with Base URL: {settings.ERP_BASE_URL}")
    print(f"Username: {settings.ERP_USERNAME}")
    print("Attempting to get token...")
    try:
        token = await erp_client._get_valid_token()
        print(f"Success! Token received: {token[:10]}... (truncated)")
        
        # Now test the example URL provided by the user
        print("\nTesting example URL: /accounting/api/vendors/invoice/get/")
        res = await erp_client.get("/accounting/api/vendors/invoice/get/")
        print("Success!", str(res)[:100])
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())