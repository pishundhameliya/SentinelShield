---
name: costwise
description: High-efficiency token optimization, AST symbol search, and automated setup protocol for CostWise MCP
---

# CostWise MCP Protocol & Automated Setup

## 1. Automated Setup Protocol (If Missing on Device)
If the CostWise MCP server is not registered or available in the current agent environment:
1. Run the universal automated installer:
   ```bash
   python scripts/setup_costwise.py
   ```
2. The script will automatically:
   - Detect `npm` / `pip` / `npx` and install `costwise-mcp`.
   - Provision `.mcp.json`, `.cursor/mcp.json`, and `.vscode/settings.json`.
   - Index the codebase for AST symbol lookup.

---

## 2. Core Tool Selection Hierarchy

| Task | Preferred CostWise Tool | Prohibited Action |
| :--- | :--- | :--- |
| **Understand repo structure** | `get_repository_summary` | Broad recursive `list_dir` |
| **Find a class, function, or service** | `find_symbol(name=...)` | Raw `grep_search` across whole repo |
| **Read a specific function implementation** | `read_symbol(name=...)` | `view_file` on 800+ lines |
| **Locate callers of a function** | `find_callers(name=...)` | Manual string searches |
| **Find references to a type** | `find_references(name=...)` | Guessing import locations |
| **Search semantic concepts** | `search_code(query=...)` | Inefficient brute-force greps |
| **Park large outputs (>500 tokens)** | `stash_context(content=...)` | Pasting huge blobs into conversation |
| **Retrieve stashed context** | `recall(source=handle, query=...)` | Re-running expensive operations |
| **Targeted code edit** | `replace_file_content` | Overwriting full files with small edits |

---

## 3. Session Best Practices
- **Start with `session_brief`**: Catch up on prior context before re-deriving facts.
- **Route large outputs out of context**: Call `stash_context` to park large logs or diffs, getting a short handle.
- **Targeted Edits**: Only use `view_file` when making a targeted line-level edit after a CostWise tool has identified the exact line range.
