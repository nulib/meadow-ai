import asyncio
import json
import requests
from claude_code_sdk import (
    ClaudeSDKClient,
    ClaudeCodeOptions,
    tool,
    create_sdk_mcp_server
)
from typing import Any

# Recreate tools and options if needed
if 'metadata_server' not in globals():
    @tool("call_graphql_endpoint", "Call a GraphQL endpoint", {
        "graphql_query": str,
        "graphql_vars": dict
    })
    async def call_graphql_endpoint_tool(args: dict[str, Any]) -> dict[str, Any]:
        graphql_query = args.get("graphql_query", "")
        graphql_vars = args.get("graphql_vars", {})

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {graphql_auth_token}"
        }

        response = requests.post(graphql_endpoint, json={"query": graphql_query, "variables": graphql_vars}, headers=headers)
        if response.status_code == 200:
            return {"content": [{"type": "text", "text": json.dumps(response.json())}]}
        else:
            return {"content": [{"type": "text", "text": f"Error: {response.status_code} - {response.text}"}]}
    
    @tool("generate_keywords", "Generate relevant keywords from content", {
        "content": str,
        "context": str,
        "max_keywords": int
    })
    async def generate_keywords_tool(args: dict[str, Any]) -> dict[str, Any]:
        content = args.get("content", "")
        context = args.get("context", "")
        max_keywords = args.get("max_keywords", 10)

        import re
        words = re.findall(r'\b\w+\b', content.lower())
        context_words = re.findall(r'\b\w+\b', context.lower()) if context else []

        all_words = words + context_words
        word_freq = {}
        for word in all_words:
            if len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1

        keywords = sorted(word_freq.keys(), key=lambda x: word_freq[x], reverse=True)[:max_keywords]

        return {
            "content": [{
                "type": "text",
                "text": ", ".join(keywords)
            }]
        }

    @tool("generate_description", "Generate a description from content", {
        "content": str,
        "context": str,
        "max_length": int
    })
    async def generate_description_tool(args: dict[str, Any]) -> dict[str, Any]:
        content = args.get("content", "")
        context = args.get("context", "")
        max_length = args.get("max_length", 400)

        description = f"Analysis of content"
        if context:
            description += f" in context of {context}"
        description += f": {content[:100]}..."

        if len(description) > max_length:
            description = description[:max_length-3] + "..."

        return {
            "content": [{
                "type": "text",
                "text": description
            }]
        }

    metadata_server = create_sdk_mcp_server(
        name="metadata",
        version="1.0.0",
        tools=[call_graphql_endpoint_tool]
    )

    client_options = ClaudeCodeOptions(
        mcp_servers={"metadata": metadata_server},
        allowed_tools=[
            "mcp__metadata__call_graphql_endpoint",
        ]
    )

    print("Created MCP server.")
    print(f"Client options configured with allowed tools: {client_options.allowed_tools}")
    print("Tools registered successfully")

async def query_claude_general_local(prompt, context_json):
    context_data = json.loads(context_json) if context_json else {}

    # Build a more explicit prompt that encourages tool usage
    enhanced_prompt = f"""You have access to these tools:
    - generate_keywords: Generate relevant keywords from content
    - generate_description: Generate a description from content

    User query: {prompt}

    Context data: {json.dumps(context_data, indent=2) if context_data else "None"}

    Please use the appropriate tools to help answer this query. For example:
    - If asked to extract keywords, use the generate_keywords tool
    - If asked to create descriptions, use the generate_description tool
    - Use tools even if you could answer without them, as they provide structured analysis

    Respond with both tool results and your analysis."""

    async with ClaudeSDKClient(options=client_options) as client:
        await client.query(enhanced_prompt)
        conversation_log = []

        final_result = ""

        async for message in client.receive_response():
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        # Claude's text responses - don't store, just log
                        print(f"CLAUDE: {block.text}")
                    elif hasattr(block, 'tool_use_id'):
                        # Tool execution results - extract and immediately log
                        if isinstance(block.content, list) and len(block.content) > 0:
                            tool_text = block.content[0].get('text', str(block.content))
                            tool_output = f"🔧 Tool Result: {tool_text}"
                        else:
                            tool_output = f"🔧 Tool Result: {block.content}"

                        print(f"TOOL OUTPUT: {tool_output}")  # Log immediately

                    elif hasattr(block, 'name'):  # Tool use block
                        tool_args = getattr(block, 'input', {})
                        tool_call = f"🛠️  Using tool '{block.name}' with args: {tool_args}"
                        print(f"TOOL CALL: {tool_call}")  # Log immediately

            elif hasattr(message, 'result'):
                # Final result from ResultMessage - this is what we return
                if message.result:
                    final_result = message.result
                    print(f"FINAL: {final_result}")

        # Return just the final result content
        return final_result or "No result generated"

# Execute the query
asyncio.run(query_claude_general_local(prompt, context_json))