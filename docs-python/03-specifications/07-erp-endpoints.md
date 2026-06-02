# 07 - ERP Backend Endpoints Specification

This document outlines the required API endpoints that must be implemented in the Django ERP backend (`ai_endpoint.py`) for the AI Chatbot to function correctly.

## 1. Available Pricelists Endpoint

**Objective:** Allow the AI to proactively fetch a list of available pricelists and present them to the user, eliminating the need for the user to guess an internal `pricelist_id`.

**Endpoint:** `GET inventory/api/ai/pricelists/`

**Headers Required:**
*   `Authorization: Bearer <TOKEN>` (Standard ERP token auth via `erp_client`)

**Expected Response Format (JSON):**
The endpoint must return an array of objects. Each object should represent a pricelist and contain at least an `id` and a `name`.

```json
[
  {
    "id": "1",
    "name": "Eceran (Retail)"
  },
  {
    "id": "2",
    "name": "Grosir (Wholesale)"
  },
  {
    "id": "3",
    "name": "Distributor"
  }
]
```

**Notes for Implementation:**
*   Ensure the `id` corresponds to the exact value expected by the `inventory/api/ai/pricelist-detail/` endpoint.
*   The `name` should be a human-readable string that the AI can present to the customer.
