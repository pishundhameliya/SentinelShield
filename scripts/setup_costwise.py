#!/usr/bin/env python3
"""Automated CostWise MCP Installer & Configuration Daemon for SentinelShield.

Detects if CostWise MCP is installed on the host system. If not present,
it automatically installs CostWise via npm / pip / npx and provisions
configuration files for Cursor, Claude Code, Windsurf, and VSCode.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    """Execute command safely and capture output."""
    try:
        proc = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def is_tool_installed(name: str) -> bool:
    """Check if binary executable is available on PATH."""
    return shutil.which(name) is not None


def ensure_mcp_configs():
    """Ensure standard MCP config files exist for all major agent IDEs."""
    mcp_config = {
        "mcpServers": {
            "costwise": {
                "command": "costwise-mcp" if is_tool_installed("costwise-mcp") else "npx",
                "args": [] if is_tool_installed("costwise-mcp") else ["-y", "costwise-mcp"],
                "env": {
                    "COSTWISE_WORKSPACE": "${workspaceFolder}"
                },
                "description": "CostWise MCP Server — AST symbol indexing, code search, and context stashing"
            }
        }
    }

    # 1. Root .mcp.json (Standard)
    root_mcp_path = os.path.join(BASE_DIR, ".mcp.json")
    with open(root_mcp_path, "w", encoding="utf-8") as f:
        json.dump(mcp_config, f, indent=2)
    print(f" [OK] Configured root MCP: {os.path.relpath(root_mcp_path, BASE_DIR)}")

    # 2. .cursor/mcp.json (Cursor IDE)
    cursor_dir = os.path.join(BASE_DIR, ".cursor")
    os.makedirs(cursor_dir, exist_ok=True)
    cursor_mcp_path = os.path.join(cursor_dir, "mcp.json")
    with open(cursor_mcp_path, "w", encoding="utf-8") as f:
        json.dump(mcp_config, f, indent=2)
    print(f" [OK] Configured Cursor MCP: {os.path.relpath(cursor_mcp_path, BASE_DIR)}")

    # 3. .vscode/settings.json (VSCode / Claude)
    vscode_dir = os.path.join(BASE_DIR, ".vscode")
    os.makedirs(vscode_dir, exist_ok=True)
    vscode_settings_path = os.path.join(vscode_dir, "settings.json")
    settings = {}
    if os.path.exists(vscode_settings_path):
        try:
            with open(vscode_settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
    settings["costwise.enabled"] = True
    settings["costwise.autoIndex"] = True
    with open(vscode_settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    print(f" [OK] Configured VSCode settings: {os.path.relpath(vscode_settings_path, BASE_DIR)}")


def setup_costwise() -> int:
    print("================================================================================")
    print("           SENTINELSHIELD — COSTWISE MCP AUTO-INSTALLER & PROVISIONER           ")
    print("================================================================================")

    # Check if costwise-mcp is already installed
    if is_tool_installed("costwise-mcp"):
        print(" [FOUND] CostWise MCP binary ('costwise-mcp') is already installed on PATH.")
        ensure_mcp_configs()
        print(" [ALL READY] CostWise MCP is fully provisioned and ready for agent sessions.")
        return 0

    print(" [MISSING] 'costwise-mcp' was not found on system PATH. Attempting automatic install...")

    # Attempt 1: npm install -g costwise-mcp
    if is_tool_installed("npm"):
        print(" -> Attempting global npm installation (npm install -g costwise-mcp)...")
        code, out, err = run_cmd(["npm", "install", "-g", "costwise-mcp"])
        if code == 0:
            print(" [SUCCESS] Installed costwise-mcp via npm globally!")
            ensure_mcp_configs()
            return 0
        else:
            print(f" [NOTICE] Global npm install failed (likely permission/sandbox). Falling back to npx/pip... ({err[:80]})")

    # Attempt 2: pip install costwise-mcp
    if is_tool_installed("pip"):
        print(" -> Attempting python pip installation (pip install costwise-mcp)...")
        code, out, err = run_cmd([sys.executable, "-m", "pip", "install", "costwise-mcp"])
        if code == 0:
            print(" [SUCCESS] Installed costwise-mcp via pip!")
            ensure_mcp_configs()
            return 0

    # Attempt 3: npx fallback configuration
    if is_tool_installed("npx"):
        print(" [FALLBACK] Provisioning zero-install dynamic execution via 'npx -y costwise-mcp'...")
        ensure_mcp_configs()
        print(" [SUCCESS] Configured npx dynamic auto-launcher for all agent environments.")
        return 0

    print(" [WARNING] Neither npm nor pip were able to complete installation.")
    print(" Please install Node.js (https://nodejs.org) or run: npm install -g costwise-mcp")
    ensure_mcp_configs()
    return 1


if __name__ == "__main__":
    sys.exit(setup_costwise())
