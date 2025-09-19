import asyncio
from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from meadow_metadata_agent.initialize import metadata_server

client_options = ClaudeCodeOptions(
    mcp_servers={"metadata": metadata_server},
    allowed_tools=[
        # "mcp__metadata__generate_keywords",
        # "mcp__metadata__generate_description",
        "mcp__metadata__call_graphql_endpoint",
    ]
)

# Global variables for client management
global_client = None
client_options_global = client_options

async def query_claude_general(prompt, context_json):
    import json
    global global_client

    # Parse context and include it in the prompt
    context_data = json.loads(context_json) if context_json else {}

    # Build enhanced prompt with context
    enhanced_prompt = prompt
    if context_data:
        enhanced_prompt += f"\n\nContext data: {json.dumps(context_data, indent=2)}"
        enhanced_prompt += "\n\nPlease use the available tools (generate_keywords, generate_description) if they would help answer this query."

    # Use client as context manager
    async with ClaudeSDKClient(options=client_options_global) as client:
        await client.query(enhanced_prompt)
        result = ""
        async for message in client.receive_response():
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        result += block.text
            elif hasattr(message, 'text'):
                result += message.text
        return result

async def ask_claude_for_keywords(content, context, max_keywords):
    prompt = f"Please analyze this content and generate {max_keywords} relevant keywords using the generate_keywords tool. Content: {content}. Context: {context}"

    async with ClaudeSDKClient(options=client_options_global) as client:
        await client.query(prompt)
        result = ""
        async for message in client.receive_response():
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        result += block.text
            elif hasattr(message, 'text'):
                result += message.text
        return result

async def ask_claude_for_description(content, context, max_length):
    prompt = f"Please analyze this content and generate a description (max {max_length} chars) using the generate_description tool. Content: {content}. Context: {context}"

    async with ClaudeSDKClient(options=client_options_global) as client:
        await client.query(prompt)
        result = ""
        async for message in client.receive_response():
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        result += block.text
            elif hasattr(message, 'text'):
                result += message.text
        return result

def generate_keywords_sync(content, context="", max_keywords=10):
    return asyncio.run(ask_claude_for_keywords(content, context, max_keywords))

def generate_description_sync(content, context="", max_length=400):
    return asyncio.run(ask_claude_for_description(content, context, max_length))

def query_claude_sync(prompt, context_json=""):
    return asyncio.run(query_claude_general(prompt, context_json))

print("MetadataAgent Python tools initialized successfully")