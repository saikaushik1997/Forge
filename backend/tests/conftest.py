import sys
import pytest_asyncio
import httpx

sys.path.insert(0, ".")

BASE_URL = "http://localhost:8001"


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as c:
        yield c
