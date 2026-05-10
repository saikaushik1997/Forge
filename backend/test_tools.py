import asyncio, os, sys
sys.path.insert(0, '.')
from config import settings

os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

async def main():
    llm = ChatAnthropic(model="claude-sonnet-4-6", api_key=settings.anthropic_api_key, max_tokens=1000)
    tools = [TavilySearchResults(max_results=2)]
    llm_with_tools = llm.bind_tools(tools, tool_choice="any")

    messages = [
        SystemMessage(content="You are a research assistant. Use web_search for any query."),
        HumanMessage(content="IPL 2026"),
    ]

    print("Calling LLM with tools bound (tool_choice=any)...")
    response = await llm_with_tools.ainvoke(messages)
    print("tool_calls:", response.tool_calls)
    print("content:", response.content[:100] if response.content else "(empty)")

asyncio.run(main())
