# Attaching Claude to the MCP server

Puts five questions to Claude that are only answerable from this server's data, and
prints which tools it reached for. It verifies nothing, and it talks to a real model on
a credential of your own, so every run costs whatever that credential is billed at.

## Where the wiki comes from

Claude is handed the server the way your own settings would hand it one: a command to
run, started as a process of its own and spoken to down a pipe. It is not fetched, not
served over http and not containerised, and it reads `data/knowledge.sqlite3`, the build
in this working copy. That is pinned by the script rather than left to a
`WIKI_API_DATA_DIR` line, so a run cannot quietly answer from a different build. Nothing
listens on a port, so there is no key to issue and none to present.

## Setting up

Create a **`.env` in this folder** (git-ignored) for the Anthropic credential:

```
CLAUDE_CODE_OAUTH_TOKEN=
```

Generate it with `claude setup-token`, which uses your Claude subscription rather than
pay-per-token credits, or leave it empty to use whatever `claude` here is signed in as.
Nothing else belongs in that file, and the script prints what to put in a missing one.

Then, from the repository root:

```bash
uv sync --all-extras
uv run poe build-artifact <documents>   # the questions here are written against it
```

## Running it

```bash
uv run poe demo claude_mcp_attach
uv run poe demo claude_mcp_attach "what does the crossbow shop sell?"
```

### Example output
```
  asked: which npcs drop a dragon scimitar?
    called mcp__2009scape-wiki__dropped_by({'name': 'dragon scimitar'})
    said: Only the King Black Dragon drops a dragon scimitar, at a 1/512 chance.
    WORKED  reached 1 tool(s) and answered from them
```

Each question ends in **WORKED** (called the server, and the answer carries a fact only
the server had), **MISSED** (never called it) or **UNSURE** (called it, but the answer
does not mention what was expected). Read the tool calls rather than the prose: they are
what tells you whether this server's published descriptions steer a model.

If `ANTHROPIC_API_KEY` is set it outranks the subscription credential and quietly
moves these runs onto pay-per-token billing, `unset` it, or check with `/status`.
