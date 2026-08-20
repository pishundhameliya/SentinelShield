# Agentic Development Directory

This directory contains specifications, workflows, and prompts for AI coding agents collaborating on the SentinelShield project.

## Agent Workflows

- **System Context**: Read `AGENTS.md` and `ARCHITECTURE.md` in the root repository before making changes.
- **Rules of Engagement**: Follow the non-negotiable rules outlined in `AGENT_RULES.md`.
- **Component Registry**: Reference `PROJECT_MANIFEST.md` for symbol and endpoint definitions.

## Key Boundaries

```
sentinelshield/core/       -> Core infrastructure (Database, Security, State)
sentinelshield/modules/    -> Domain subsystems (Vision, Streaming, Alerts, etc.)
sentinelshield/static/     -> Modular frontend (CSS, State, API, View modules)
sentinelshield/tests/      -> Verification test suite
```
