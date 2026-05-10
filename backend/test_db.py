import asyncio
import sys
sys.path.insert(0, '.')

from database import AsyncSessionLocal, create_tables
from models.agent import Agent

async def main():
    print("Creating tables...")
    await create_tables()
    print("Tables created.")

    async with AsyncSessionLocal() as db:
        print("Creating agent...")
        agent = Agent(
            name="Test",
            role="Tester",
            system_prompt="You are a test agent.",
        )
        db.add(agent)
        await db.commit()
        await db.refresh(agent)
        print(f"Agent created: {agent.id} | {agent.name} | created_at={agent.created_at}")

asyncio.run(main())
