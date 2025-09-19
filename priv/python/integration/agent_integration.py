import asyncio
from meadow_metadata_agent.execute import query_claude_general_local

asyncio.run(query_claude_general_local(prompt, context_json))
