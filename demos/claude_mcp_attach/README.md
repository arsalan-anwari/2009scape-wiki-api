# Attaching Claude to the MCP server

Puts five questions to Claude that are only answerable from this server's data, and
prints which tools it reached for. It verifies nothing but it talks to a real model, so
it needs a credential of your own.

## Setting up

Create a **`.env` in this folder** (git-ignored, so nothing here is committed):

```
CLAUDE_CODE_OAUTH_TOKEN=
```

Generate the token with `claude setup-token`, which signs in with your Claude
subscription rather than pay-per-token credits. Leave it empty to use whatever
`claude` on this machine is already signed in as. Any `WIKI_API_` setting works in
the same file. The script refuses to start without a `.env` and prints what to put
in it.

Then, from the repository root:

```bash
uv sync --extra demos
uv run poe build-artifact   # the server refuses to start without a dataset
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

Each question ends in **WORKED** (called the server, and the answer carries a fact
only the server had), **MISSED** (never called it) or **UNSURE** (called it, but the
answer does not mention what was expected). Read the tool calls rather than the
prose: they are what tells you whether the descriptions this server publishes
actually steer a model.

If `ANTHROPIC_API_KEY` is set it outranks the subscription credential and quietly
moves these runs onto pay-per-token billing, `unset` it, or check with `/status`.
