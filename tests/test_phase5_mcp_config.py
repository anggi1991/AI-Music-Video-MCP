import os
import json
import subprocess
import pytest

def test_mcp_config_exists_and_valid():
    config_path = "mcp_config.json"
    assert os.path.exists(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "mcpServers" in data
    servers = data["mcpServers"]
    assert "daw-studio-mcp" in servers
    assert "tab-transcriber-mcp" in servers
    assert "capcut-director-mcp" in servers

    for name, srv in servers.items():
        assert "command" in srv
        assert "args" in srv
        cmd = srv["command"]
        args = srv["args"]

        # Verify python interpreter exists
        assert os.path.exists(cmd), f"Interpreter for {name} does not exist: {cmd}"
        # Verify server script exists
        assert len(args) >= 1
        script_file = args[0]
        assert os.path.exists(script_file), f"Server script for {name} does not exist: {script_file}"

        # Test that server script compiles without syntax errors
        res = subprocess.run([cmd, "-m", "py_compile", script_file], capture_output=True, text=True)
        assert res.returncode == 0, f"Compilation failed for {script_file}: {res.stderr}"
