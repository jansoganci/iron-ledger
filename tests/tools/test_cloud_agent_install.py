from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cloud_agent_install_script_exists_and_uses_lockfiles() -> None:
    script_path = REPO_ROOT / ".cursor" / "install.sh"
    assert script_path.is_file()
    script = script_path.read_text(encoding="utf-8")
    assert "npm ci" in script
    assert "npm --prefix frontend ci" in script
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert "npm install" not in stripped


def test_cloud_agent_environment_json_points_at_install_script() -> None:
    env_path = REPO_ROOT / ".cursor" / "environment.json"
    config = json.loads(env_path.read_text(encoding="utf-8"))
    assert config["install"] == "bash .cursor/install.sh"
    ports = {item["port"] for item in config["ports"]}
    assert ports == {8000, 5173}
    commands = [terminal["command"] for terminal in config["terminals"]]
    assert "npm run dev" in commands
