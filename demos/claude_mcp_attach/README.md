# Attaching Claude to the MCP server

Puts five questions to Claude that are only answerable from this server's data, and
prints which tools it reached for. It verifies nothing, and it talks to a real model on
a credential of your own, so every run costs whatever that credential is billed at.

## Setting up

**Issue the wiki key first.** The tools are served over http with Claude handed a token
to present, so the run exercises the same path a shared host would, and it will not
start without one:

```bash
uv run poe keys init                     # once, if you have not already
uv run poe keys issue --label demos      # kept in tokens/demos.json
```

That file is read directly, so the token never goes in a `.env`. Point at a different
file with a `DEMO_TOKEN_FILE=` line.

Then create a **`.env` in this folder** (git-ignored) for the unrelated Anthropic
credential:

```
CLAUDE_CODE_OAUTH_TOKEN=
```

Generate it with `claude setup-token`, which uses your Claude subscription rather than
pay-per-token credits, or leave it empty to use whatever `claude` here is signed in as.
Any `WIKI_API_` setting works in the same file, and the script prints what to put in a
missing `.env`.

Then, from the repository root:

```bash
uv sync --all-extras
uv run poe build-test-artifact          # the questions here are written against it
```

Point it at that dataset with `WIKI_API_DATA_DIR=data/tests` in the same `.env`, or
build a real one and leave it pointing where the settings say.

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
