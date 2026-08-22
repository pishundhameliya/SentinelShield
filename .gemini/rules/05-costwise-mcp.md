# Antigravity Rule: CostWise MCP Token Optimization

## Tool Selection Hierarchy
1. `find_symbol(name=...)` $\rightarrow$ Locate classes, functions, routes.
2. `read_symbol(name=...)` $\rightarrow$ Read targeted symbol implementations.
3. `search_code(query=...)` $\rightarrow$ Semantic & concept searches.
4. `get_repository_summary` $\rightarrow$ Map repository structure without recursive listing.
5. `stash_context(content=...)` $\rightarrow$ Park large outputs (>500 tokens) out of prompt context.
6. `view_file` $\rightarrow$ Last resort only for targeted line edits after exact range is known.

## Auto-Setup Protocol
If CostWise MCP tools are missing, run:
```bash
python scripts/setup_costwise.py
```
