# Settling a misspelt name by asking

Puts one question to Claude under a name that answers to nothing, and watches it work
out what was meant without ever picking for you. The name is misspelt on purpose and
sits close to two different sorts of thing, so it cannot be settled by guessing:

```
tell me about the king black dragn
```

There is a `King Black Dragon` (an npc) and a `King Black Dragon Lair` (a location),
and nothing under that spelling. The tool offering close spellings refuses to run until
it is told which sort was meant, so the run has two human turns, both reaching this
script as tool calls.

The model is driven with [PydanticAI](https://ai.pydantic.dev), so this is also a second
opinion on whether the tool descriptions steer a model that is not Claude Code. It
verifies nothing, and it talks to a real model on a credential of your own, so every run
costs whatever that credential is billed at.

## How close is close

Before any model is involved, the script asks the server the same thing at different
settings and prints what came back:

```
  how close is close, asked directly:
    name               sort       k  keep  offered
    king black dragn   npc        5   0.9  King Black Dragon
    king black dragn   location   5   0.9  King Black Dragon Lair
    king black dragn   item       5   0.9  (nothing close enough)
    dragon scimmitar   item       5   0.9  Dragon scimitar
    dragon scimmitar   item       5   0.5  Dragon scimitar, Dragon bones
    dragon scimmitar   item       2   0.0  Dragon scimitar, Dragon bones
```

`k` is the most names it will offer. `keep` is the share of the best score a name must
reach to be offered at all: at `0.9` only the near certain answer survives, and lowering
it brings more of the field, down to the floor the deployment sets. The first three rows
are why the sort is asked about rather than assumed.

## Setting up

Two credentials, for two different things.

**Issue the wiki key first.** The server is started over http and presented that token
on every call, because a server you started yourself has nobody to keep out and would
prove nothing. The run will not start without one:

```bash
uv run poe keys init                     # once, if you have not already
uv run poe keys issue --label demos      # kept in tokens/demos.json
```

That file is read directly, so the token never goes in a `.env`. Point at a different
file with a `DEMO_TOKEN_FILE=` line. The server started here gets the public half only.

Then create a **`.env` in this folder** (git-ignored) for the Anthropic credential:

```
CLAUDE_CODE_OAUTH_TOKEN=
```

Generate it with `claude setup-token`, which uses your Claude subscription; an
`ANTHROPIC_API_KEY` in the same file works too and is billed per token.

A subscription token is not an api key: it goes in as a bearer token under the
`oauth-2025-04-20` beta, and that endpoint answers Claude Code, so it wants to be told
so in a system block of its own. This script sends `You are Claude Code, Anthropic's
official CLI for Claude.` as the first block and its own instructions as the second.
Fold the two together and the request is refused.

Then, from the repository root:

```bash
uv sync --all-extras
uv run poe build-test-artifact   # the questions here are written against that data
```

The run prints the port the wiki came up on and the key id it is presenting, so a
refusal is easy to tell apart from a model that simply did not call anything.

The demonstration reads `data/tests/knowledge.sqlite3` unless `WIKI_API_DATA_DIR` says
otherwise, because the misspelling it asks about is aimed at the hand-made documents.

## Running it

```bash
uv run poe demo claude_fuzzy_match              # type the answers yourself
uv run poe demo claude_fuzzy_match --scripted   # answer with the built in choices
uv run poe demo claude_fuzzy_match --answer npc --answer "King Black Dragon"
uv run poe demo claude_fuzzy_match "who drops a dragon scimmitar?"
```

### Example output

```
  the model asks: Nothing answers to "king black dragn" - which sort did you mean?
    - NPC
    - item
    - location
  your answer: npc

  the model asks: Is this the one you meant?
    - King Black Dragon
    - None of these
  your answer: King Black Dragon

    called get_thing({'name': 'king black dragn'})
    called ask_user({'question': ..., 'options': ['NPC', 'item', 'location', ...]})
    called find_close_names({'name': 'king black dragn', 'type': 'npc'})
    called find_close_names({'name': 'king black dragn', 'type': 'npc', 'keep': 0.4})
    called ask_user({'question': ..., 'options': ['King Black Dragon', 'None of these']})
    called get_thing({'name': 'King Black Dragon', 'type': 'npc'})

  what happened:
    WORKED  it asked which sort of thing before looking anything up
    WORKED  it asked for close names 2 time(s)
    WORKED  the server offered King Black Dragon
    WORKED  it came back to ask which of the close names was meant
    WORKED  the answer is about King Black Dragon
```

Five things are checked, each ending in **WORKED**, **UNSURE** (it happened, but not
the way the server asks for) or **MISSED** (it did not happen). Read the tool calls
rather than the prose: the second `find_close_names` is the model widening `keep` on its
own so the person choosing sees what else was near enough. Nothing here picks a name,
and neither will the server.
