[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![Tests](https://github.com/conda-incubator/conda-meta-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/conda-incubator/conda-meta-mcp/actions/workflows/tests.yml)

# conda-meta-mcp

An MCP (Model Context Protocol) server exposing authoritative, read-only Conda ecosystem metadata for AI agents.

## What “Meta” Means Here

“Meta” refers to structured, machine-consumable ecosystem intelligence about packages — not the upstream project documentation itself. This server provides (see the schema [server-info.json](server-info.json) for current capabilities):

Currently available:

- Version metadata (MCP tool/library versions) via the `info` tool
- Package info tarball data via the `package_insights` tool
- Package search via the `package_search` tool
- Import to package heuristic mapping via the `import_mapping` tool
- CLI help (for conda) via the `cli_help` tool

Planned:

- Dependency & version metadata (graph / availability slices)
- Solver feasibility signals (dry-run outputs)
- Schema references and selected spec excerpts
- Binary linkage information
- Links (not copies) to sections of knowledge bases

It does not embed, index, or serve full library docs (e.g. numpy API pages); that remains out of scope by design.

## 1. Purpose

Enable agents to answer packaging questions by providing up-to-date critical and fragmented expert knowledge. This project provides a safe, inspectable, zero‑side‑effect surface so agents deliver accurate, up‑to‑date guidance.

## 2. Scope

### Goals

- Trustworthy machine interface
- Read‑only, hostable, air‑gap friendly
- Fast startup, low latency
- Clear extension & testing pattern

### Non‑Goals

- Performing installs / mutations
- Replacing human docs
- Re‑implementing conda‑forge processing logic

## 3. Design Principles

- Side‑effect free by contract
- Tool registration pattern (`conda_meta_mcp.tools`)
- Test + pre‑commit enforced consistency
- Incremental expansion

## 4. Quick Start

```shell
git clone https://github.com/conda-incubator/conda-meta-mcp.git
cd conda-meta-mcp
pixi run cmm --help
```

The `pixi` command can be used to run the MCP locally in clients such as VSCode, Cursor, Claude Desktop, and Zed:

```json
{
  "conda-meta-mcp": {
    "command": "pixi",
    "args": [
      "run",
      "--manifest-path",
      "/path/to/pyproject.toml",
      "cmm",
      "run",
      "-v"
    ],
    "env": {}
  }
}
```

Or call `pixi run cmm mcp-json`, which emits a JSON snippet with absolute paths that can be pasted into an MCP client configuration.

## 5. Usage inside GitHub Copilot coding agent

Create a GitHub workflow named `copilot-setup-steps.yml` containing (see also [GitHub Documentation](https://docs.github.com/en/enterprise-cloud@latest/copilot/how-tos/use-copilot-agents/coding-agent/customize-the-agent-environment)):

```yaml
jobs:
  copilot-setup-steps:
    ...
    steps:
      ...
      - name: Setup conda-meta-mcp
        uses: conda-incubator/conda-meta-mcp@main
      ...
```

Add this MCP configuration inside your repository under Settings -> Copilot -> Coding agent -> MCP Configuration:

```json
{
  "mcpServers": {
    "conda-meta-mcp": {
      "type": "local",
      "command": "cmm",
      "args": [
        "run"
      ],
      "tools": [
        "*"
      ]
    }
  }
}
```

## 6. Development

Tasks (pixi):

- Tests: `pixi run test` (for coverage open `htmlcov/index.html`)
- Lint / format / type / regenerate metadata: `pixi run pre-commit`

## 7. Extending (New Tool)

1. Add `conda_meta_mcp/tools/<name>.py` (see existing tools)
1. Implement `register_<name>` with an `@mcp.tool` async function
1. Append to `TOOLS` in `tools/__init__.py`
1. Add unit tests (mock heavy deps)
1. `pixi run pre-commit`
1. `pixi run test`
1. Open PR

## 8. Safety Model

- No environment mutation
- No external command side effects
- Future additions must preserve read‑only contract
