import httpx, asyncio

async def main():
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "http://localhost:8001/api/agents/",
            json={"name": "Test", "role": "Tester", "system_prompt": "You are a test agent."},
        )
        print("Status:", r.status_code)
        print("Body:", r.text)

asyncio.run(main())
