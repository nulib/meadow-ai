import os
from claude_code_sdk import create_sdk_mcp_server
from .tools import (
    call_graphql_endpoint_tool,
    generate_description_tool,
    generate_keywords_tool,
)

aws_bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
use_bedrock = os.getenv("CLAUDE_CODE_USE_BEDROCK") == "1" if aws_bearer_token else False
aws_region = os.getenv("AWS_REGION", "us-east-1")

if use_bedrock:
    print(f"Configured for AWS Bedrock in region: {aws_region}")
else:
    print("Using Anthropic API (not Bedrock)")

# Create MCP server with our tools
metadata_server = create_sdk_mcp_server(
    name="metadata",
    version="1.0.0",
    tools=[call_graphql_endpoint_tool, generate_keywords_tool, generate_description_tool]
)
