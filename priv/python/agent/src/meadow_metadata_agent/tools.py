from claude_code_sdk import tool
from typing import Any
import json
import os
import requests

@tool("call_graphql_endpoint", "Call a GraphQL endpoint", {
    "graphql_query": str,
    "graphql_vars": dict
})
async def call_graphql_endpoint_tool(args: dict[str, Any]) -> dict[str, Any]:
    graphql_query = args.get("graphql_query", "")
    graphql_vars = args.get("graphql_vars", {})

    graphql_endpoint = args.get("graphql_endpoint") or os.getenv("GRAPHQL_ENDPOINT")
    graphql_auth_token = args.get("graphql_auth_token") or os.getenv("GRAPHQL_AUTH_TOKEN")

    headers = {
        "Content-Type": "application/json",
    }
    if graphql_auth_token:
        headers["Authorization"] = f"Bearer {graphql_auth_token}"

    if not graphql_endpoint:
        return {"content": [{"type": "text", "text": "Error: GraphQL endpoint not provided"}]}

    response = requests.post(
        graphql_endpoint,
        json={"query": graphql_query, "variables": graphql_vars},
        headers=headers,
        timeout=30,
    )
    if response.status_code == 200:
        return {"content": [{"type": "text", "text": json.dumps(response.json())}]}
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
