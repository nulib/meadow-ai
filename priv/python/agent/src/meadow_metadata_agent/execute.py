import asyncio
import json
from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from meadow_metadata_agent.initialize import metadata_server

client_options = ClaudeCodeOptions(
    mcp_servers={"metadata": metadata_server},
    allowed_tools=[
        # "mcp__metadata__generate_keywords",
        # "mcp__metadata__generate_description",
        "mcp__metadata__call_graphql_endpoint",
    ],
    disallowed_tools=["Bash", "Grep"],
    system_prompt="Answer questions ONLY using the graphql tools available. Do not look for information in the file system or local codebase."
)

# Global variables for client management
global_client = None
client_options_global = client_options

async def query_claude_general(prompt, context_json):
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

async def query_claude_general_local(prompt, context_json):
    context_data = json.loads(context_json) if context_json else {}

    # Build a more explicit prompt that encourages tool usage
    enhanced_prompt = f"""
    Use the available tools to answer the following query:

    User query: {prompt}

    Context data: {json.dumps(context_data, indent=2) if context_data else "None"}

    Please use the appropriate tools to help answer this query. For example:
    - Before using the `call_graphql_endpoint` tool to query or update data, use it to discover the schema first.

    Respond with both tool results and your analysis."""

    async with ClaudeSDKClient(options=client_options) as client:
        await client.query(enhanced_prompt)
        conversation_log = []

        final_result = ""

        async for message in client.receive_response():
            print(f"MESSAGE: {message}")
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