defmodule MeadowAI.MixProject do
  use Mix.Project

  def project do
    [
      app: :meadow_ai,
      version: "0.1.0",
      elixir: "~> 1.18",
      start_permanent: Mix.env() == :prod,
      deps: deps(),
      aliases: aliases()
    ]
  end

  # Run "mix help compile.app" to learn about applications.
  def application do
    [
      extra_applications: [:logger],
      mod: {MeadowAI.Application, []}
    ]
  end

  # Run "mix help deps" to learn about dependencies.
  defp deps do
    [
      {:pythonx, "~> 0.4.0"},
      {:jason, "~> 1.4"}
    ]
  end

  # Aliases for common tasks
  defp aliases do
    [
      precommit: ["format", "compile", "test --color"]
    ]
  end

  def cli do
    [
      preferred_envs: [precommit: :test]
    ]
  end
end
