defmodule MeadowAI.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      # MetadataAgent for AI-powered metadata generation
      {MeadowAI.MetadataAgent, []}
      # Starts a worker by calling: MeadowAI.Worker.start_link(arg)
      # {MeadowAI.Worker, arg}
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: MeadowAI.Supervisor]
    Supervisor.start_link(children, opts)
  end
end
