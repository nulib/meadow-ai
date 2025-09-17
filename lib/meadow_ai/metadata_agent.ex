defmodule MeadowAI.MetadataAgent do
  use GenServer
  require Logger

  @moduledoc """
  A GenServer that wraps PythonX functionality and provides AI-powered metadata generation tools.

  This agent integrates with the Claude Code Python SDK to provide:
  - Keyword generation from content and context via Claude using custom tools
  - Description generation for metadata purposes via Claude using custom tools
  - Session management and error recovery
  """

  # Client API

  def start_link(opts \\ []) do
    GenServer.start_link(__MODULE__, opts, name: __MODULE__)
  end

  @doc """
  Send a natural language query to Claude with optional context.

  Claude will intelligently choose which tools to use based on your request.

  ## Parameters
  - prompt: Natural language query
  - opts: Optional parameters including :context and :timeout

  ## Returns
  {:ok, response} | {:error, reason}
  """
  def query(prompt, opts \\ []) do
    timeout = Keyword.get(opts, :timeout, 30_000)
    GenServer.call(__MODULE__, {:query, prompt, opts}, timeout)
  end


  @doc """
  Gets the current status of the MetadataAgent.
  """
  def status do
    GenServer.call(__MODULE__, :status)
  end

  @doc """
  Restarts the Python session (useful for recovery).
  """
  def restart_session do
    GenServer.call(__MODULE__, :restart_session, 60_000)
  end

  # Server Callbacks

  @impl true
  def init(opts) do
    Logger.info("Starting MetadataAgent...")

    case initialize_python_session(opts) do
      {:ok, session_info} ->
        state = %{
          python_initialized: true,
          session_info: session_info,
          startup_time: DateTime.utc_now(),
          request_count: 0,
          failure_count: 0,
          last_failure: nil,
          circuit_breaker_state: :closed
        }
        Logger.info("MetadataAgent started successfully")
        {:ok, state}

      {:error, reason} ->
        Logger.error("Failed to initialize MetadataAgent: #{inspect(reason)}")
        {:stop, reason}
    end
  end

  @impl true
  def handle_call({:query, prompt, opts}, _from, state) do
    case state.python_initialized do
      true ->
        result = execute_claude_query(prompt, opts)
        new_state = %{state | request_count: state.request_count + 1}
        {:reply, result, new_state}

      false ->
        Logger.warning("MetadataAgent: Python session not initialized, attempting restart...")
        case initialize_python_session([]) do
          {:ok, session_info} ->
            new_state = %{state | python_initialized: true, session_info: session_info}
            result = execute_claude_query(prompt, opts)
            {:reply, result, %{new_state | request_count: new_state.request_count + 1}}

          {:error, reason} ->
            {:reply, {:error, {:session_unavailable, reason}}, state}
        end
    end
  end


  @impl true
  def handle_call(:status, _from, state) do
    status_info = %{
      python_initialized: state.python_initialized,
      startup_time: state.startup_time,
      request_count: state.request_count,
      uptime_seconds: DateTime.diff(DateTime.utc_now(), state.startup_time)
    }
    {:reply, {:ok, status_info}, state}
  end

  @impl true
  def handle_call(:restart_session, _from, state) do
    Logger.info("Restarting Python session...")

    case initialize_python_session([]) do
      {:ok, session_info} ->
        new_state = %{
          state |
          session_info: session_info,
          startup_time: DateTime.utc_now()
        }
        Logger.info("Python session restarted successfully")
        {:reply, :ok, new_state}

      {:error, reason} ->
        Logger.error("Failed to restart Python session: #{inspect(reason)}")
        {:reply, {:error, reason}, state}
    end
  end

  @impl true
  def handle_info(msg, state) do
    Logger.debug("MetadataAgent received unexpected message: #{inspect(msg)}")
    {:noreply, state}
  end

  @impl true
  def terminate(reason, _state) do
    Logger.info("MetadataAgent terminating: #{inspect(reason)}")
    :ok
  end

  # Private Functions

  defp initialize_python_session(_opts) do
    try do
      # Check for Bedrock configuration
      aws_bearer_token = System.get_env("AWS_BEARER_TOKEN_BEDROCK")
      use_bedrock = !is_nil(aws_bearer_token) || System.get_env("CLAUDE_CODE_USE_BEDROCK") == "1"
      aws_region = System.get_env("AWS_REGION", "us-east-1")
      aws_access_key_id = System.get_env("AWS_ACCESS_KEY_ID")
      aws_secret_access_key = System.get_env("AWS_SECRET_ACCESS_KEY")
      aws_session_token = System.get_env("AWS_SESSION_TOKEN")
      max_output_tokens = System.get_env("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "4096")
      max_thinking_tokens = System.get_env("MAX_THINKING_TOKENS", "1024")

      Logger.info("Initializing MetadataAgent with Bedrock: #{use_bedrock}, Region: #{aws_region}")

      # Initialize PythonX with Claude Code Python SDK
      python_config = """
      [project]
      name = "meadow-metadata-agent"
      version = "0.1.0"
      requires-python = ">=3.11"
      dependencies = [
        "claude-code-sdk>=0.0.22",
        "boto3>=1.34.0"
      ]
      """

      case Pythonx.uv_init(python_config) do
        :ok ->
          # Set up the Python environment with our tools
          setup_result =
            Pythonx.eval(
              """
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

              # Configure AWS environment variables for Bedrock
              use_bedrock = #{if use_bedrock, do: "True", else: "False"}
              aws_bearer_token = #{inspect(aws_bearer_token || "")}
              aws_region = #{inspect(aws_region)}
              aws_access_key_id = #{inspect(aws_access_key_id || "")}
              aws_secret_access_key = #{inspect(aws_secret_access_key || "")}
              aws_session_token = #{inspect(aws_session_token || "")}
              max_output_tokens = #{inspect(max_output_tokens)}
              max_thinking_tokens = #{inspect(max_thinking_tokens)}

              if use_bedrock:
                  os.environ['CLAUDE_CODE_USE_BEDROCK'] = '1'
                  os.environ['AWS_REGION'] = aws_region

                  # Priority: Bearer token first, then access key/secret, then session token
                  if aws_bearer_token and aws_bearer_token != "":
                      os.environ['AWS_BEARER_TOKEN_BEDROCK'] = aws_bearer_token
                      print(f"Configured for AWS Bedrock with bearer token in region: {aws_region}")
                  elif aws_access_key_id and aws_access_key_id != "" and aws_secret_access_key and aws_secret_access_key != "":
                      os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key_id
                      os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_access_key
                      if aws_session_token and aws_session_token != "":
                          os.environ['AWS_SESSION_TOKEN'] = aws_session_token
                      print(f"Configured for AWS Bedrock with access key in region: {aws_region}")
                  else:
                      print(f"Configured for AWS Bedrock (using default credentials) in region: {aws_region}")

                  os.environ['CLAUDE_CODE_MAX_OUTPUT_TOKENS'] = max_output_tokens
                  os.environ['MAX_THINKING_TOKENS'] = max_thinking_tokens
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
                  words = re.findall(r'\\b\\w+\\b', content.lower())
                  context_words = re.findall(r'\\b\\w+\\b', context.lower()) if context else []

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
                      enhanced_prompt += f"\\n\\nContext data: {json.dumps(context_data, indent=2)}"
                      enhanced_prompt += "\\n\\nPlease use the available tools (generate_keywords, generate_description) if they would help answer this query."

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
              """,
              %{}
            )

          case setup_result do
            {_output, _globals} ->
              {:ok, %{initialized_at: DateTime.utc_now()}}
          end

        _ ->
          {:error, :pythonx_init_failed}
      end
    rescue
      error ->
        {:error, {:initialization_error, error}}
    end
  end

  defp execute_claude_query(prompt, opts) do
    try do
      context = Keyword.get(opts, :context, %{})

      if String.length(prompt) > 10_000 do
        {:error, {:input_too_large, "Prompt exceeds 10,000 characters"}}
      else
        # Serialize context as JSON for Python
        context_json = Jason.encode!(context)

        # Ensure function exists and call it
        query_code = """
        import asyncio
        import json
        from claude_code_sdk import (
            ClaudeSDKClient,
            ClaudeCodeOptions,
            tool,
            create_sdk_mcp_server
        )
        from typing import Any

        # Recreate tools and options if needed
        if 'metadata_server' not in globals():
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
                words = re.findall(r'\\b\\w+\\b', content.lower())
                context_words = re.findall(r'\\b\\w+\\b', context.lower()) if context else []

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
                tools=[generate_keywords_tool, generate_description_tool]
            )

            client_options = ClaudeCodeOptions(
                mcp_servers={"metadata": metadata_server},
                allowed_tools=[
                    "mcp__metadata__generate_keywords",
                    "mcp__metadata__generate_description"
                ]
            )

            print(f"Created MCP server with {len([generate_keywords_tool, generate_description_tool])} tools")
            print(f"Client options configured with allowed tools: {client_options.allowed_tools}")
            print("Tools registered successfully")

        async def query_claude_general_local(prompt, context_json):
            context_data = json.loads(context_json) if context_json else {}

            # Build a more explicit prompt that encourages tool usage
            enhanced_prompt = f\"\"\"You have access to these tools:
            - generate_keywords: Generate relevant keywords from content
            - generate_description: Generate a description from content

            User query: {prompt}

            Context data: {json.dumps(context_data, indent=2) if context_data else "None"}

            Please use the appropriate tools to help answer this query. For example:
            - If asked to extract keywords, use the generate_keywords tool
            - If asked to create descriptions, use the generate_description tool
            - Use tools even if you could answer without them, as they provide structured analysis

            Respond with both tool results and your analysis.\"\"\"

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
        asyncio.run(query_claude_general_local(#{inspect(prompt)}, #{inspect(context_json)}))
        """

        result = Pythonx.eval(query_code, %{})
        case result do
          {response, _globals} -> {:ok, parse_claude_response(response)}
          error -> {:error, {:pythonx_eval_error, error}}
        end
      end
    rescue
      error ->
        Logger.error("Claude query execution error: #{inspect(error)}")
        {:error, {:query_execution_error, error}}
    end
  end


  defp parse_claude_response(response) when is_binary(response) do
    String.trim(response)
  end

  defp parse_claude_response(%Pythonx.Object{} = response) do
    # Pythonx.decode returns the value directly, not wrapped in {:ok, result}
    try do
      decoded = Pythonx.decode(response)
      if is_binary(decoded) do
        String.trim(decoded)
      else
        to_string(decoded) |> String.trim()
      end
    rescue
      error ->
        Logger.warning("Failed to decode Pythonx.Object: #{inspect(error)}")
        # Fallback: extract from inspect output
        response
        |> inspect()
        |> String.replace(~r/#Pythonx\.Object<\s*"(.*)"\s*>/, "\\1")
        |> String.replace("\\n", "\n")  # Fix escaped newlines
        |> String.trim()
    end
  end

  defp parse_claude_response(response), do: to_string(response) |> String.trim()
end
