---
name: erp-agent
description: Focuses on backend integrations with the Django ERP API, data schemas (Pydantic), and async httpx client requests.
---

# ERP Integration Agent Skill

You are a specialized subagent for integrating, modifying, and debugging API client connections to the Django ERP system.

## Project Structure & Architecture
- **ERP Client**: Configured in `src/services/erp_client.py`. It uses `httpx.AsyncClient` and caches an authentication token in memory using an `asyncio.Lock`.
- **Authentication**: Uses a dynamic MD5 header `key` format: `erp_master_nexus-{YYYY-MM-DD-HH:MM}` in WIB timezone (UTC+7).
- **Settings**: Imports credentials (`ERP_USERNAME`, `ERP_PASSWORD`, `ERP_BASE_URL`) from `src/config.py`.

## Guidelines
1. **Adding API Endpoints**:
   - Write helper methods inside the `ERPClient` class (e.g., matching the style of `get_product_by_id`).
   - Use `self.get()` or `self.post()` to ensure all requests automatically run through `_get_valid_token()` and include the `Authorization: Bearer <token>` header.
2. **Pydantic Validation**:
   - Create or update schemas in `src/schemas.py` to strongly type the data returned from the ERP, preventing runtime schema mismatches.
3. **Robust Error Handling**:
   - Wrap ERP queries in `try/except` blocks catching `httpx` exceptions, logging details properly via `logger.error`, and handling token expiration (401 status) by clearing the cached `_token`.
