import asyncio
from meadow_metadata_agent.execute import query_claude_general

asyncio.run(query_claude_general(prompt, context_json))
