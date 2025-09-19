import Config

if File.exists?("config/#{Mix.env()}.exs") do
  import_config "#{Mix.env()}.exs"
end

if File.exists?("config/#{Mix.env()}.local.exs") do
  import_config "#{Mix.env()}.local.exs"
end
