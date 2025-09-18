import asyncio
import os
from claude_code_sdk import (
    ClaudeSDKClient,
    ClaudeCodeOptions,
    tool,
    create_sdk_mcp_server,
    AssistantMessage,
    TextBlock
)
from typing import Any

aws_bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
use_bedrock = os.getenv("CLAUDE_CODE_USE_BEDROCK") == "1" if aws_bearer_token else False
aws_region = os.getenv("AWS_REGION", "us-east-1")
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_session_token = os.getenv("AWS_SESSION_TOKEN")
max_output_tokens = os.getenv("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "4096")
max_thinking_tokens = os.getenv("MAX_THINKING_TOKENS", "1024")

if use_bedrock:
    print(f"Configured for AWS Bedrock in region: {aws_region}")
else:
    print("Using Anthropic API (not Bedrock)")

# Define generate_keywords tool
@tool("generate_keywords", "Generate relevant keywords from content", {
    "content": str,
    "context": str,
    "max_keywords": int
})
async def generate_keywords_tool(args: dict[str, Any]) -> dict[str, Any]:
    content = args.get("content", "")
    context = args.get("context", "")
    max_keywords = args.get("max_keywords", 10)

    # Simple keyword extraction using basic NLP
    import re
    words = re.findall(r'\b\w+\b', content.lower())
    context_words = re.findall(r'\b\w+\b', context.lower()) if context else []

    # Combine and filter words
    all_words = words + context_words
    word_freq = {}
    for word in all_words:
        if len(word) > 3:  # Filter short words
            word_freq[word] = word_freq.get(word, 0) + 1

    # Get top keywords
    keywords = sorted(word_freq.keys(), key=lambda x: word_freq[x], reverse=True)[:max_keywords]

    return {
        "content": [{
            "type": "text",
            "text": ", ".join(keywords)
        }]
    }

# Define generate_description tool
@tool("generate_description", "Generate a description from content", {
    "content": str,
    "context": str,
    "max_length": int
})
async def generate_description_tool(args: dict[str, Any]) -> dict[str, Any]:
    content = args.get("content", "")
    context = args.get("context", "")
    max_length = args.get("max_length", 400)

    # Simple description generation
    description = f"Analysis of content"
    if context:
        description += f" in context of {context}"
    description += f": {content[:100]}..."

    # Trim to max length if needed
    if len(description) > max_length:
        description = description[:max_length-3] + "..."

    return {
        "content": [{
            "type": "text",
            "text": description
        }]
    }

# Create MCP server with our tools
metadata_server = create_sdk_mcp_server(
    name="metadata",
    version="1.0.0",
    tools=[generate_keywords_tool, generate_description_tool]
)

# Configure options with the server
client_options = ClaudeCodeOptions(
    mcp_servers={"metadata": metadata_server},
    allowed_tools=[
        "mcp__metadata__generate_keywords",
        "mcp__metadata__generate_description"
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