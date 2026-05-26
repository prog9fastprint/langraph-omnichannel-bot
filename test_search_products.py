import asyncio
import os
import sys

# Add current dir to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.agent.tools import search_products

async def main():
    try:
        print("Testing search_products...")
        # invoke with empty config or valid input
        res = await search_products.ainvoke({"filter": "1012"})
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
