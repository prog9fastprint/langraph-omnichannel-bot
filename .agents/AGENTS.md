# Project-Scoped Rules for Python Omnichannel AI

The following rules apply universally to all agents working in this project. You must strictly follow these behavioral constraints and coding style guidelines.

## 1. Asynchronous & Typed Code
- **Always use `async/await`**: This is a high-concurrency FastAPI/LangGraph application. Ensure all I/O bound operations (API calls, DB queries, file reads) are asynchronous.
- **Type Hinting**: Always use strict type hinting (e.g., `list[str]`, `dict`, `int | None`) for all new code and function signatures.

## 2. Single Source of Truth (ERP Integration)
- **No Local Business Database**: Never attempt to connect to a local database directly for business logic or product data. 
- **Query via API**: Always query the central Django ERP system via the provided HTTP API (using `src.services.erp_client`) for live product, stock, and pricing data.

## 3. Testing Standard
- **Pytest**: Always write unit and integration tests using `pytest` for any newly added endpoints, logic, or Pydantic schemas.

## 4. Logging vs Printing
- **Use Logging Module**: Never use standard `print()` statements for debugging or output in production code.
- **Implementation**: Always instantiate a logger at the top of the file (`logger = logging.getLogger(__name__)`) and use `logger.info`, `logger.warning`, or `logger.error` to properly track execution and errors.
