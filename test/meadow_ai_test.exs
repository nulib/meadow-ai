defmodule MeadowAITest do
  use ExUnit.Case
  doctest MeadowAI

  test "greets the world" do
    assert MeadowAI.hello() == :world
  end
end
