# How much can this wiki actually be asked?

Puts twenty-five questions of different shapes to Claude, one per capability rather than
one per tool, and counts what came back. The point is not that any single answer is
right; it is the tally at the end, which says how much of the data model a question can
reach today and which tools nothing thought to call. It verifies nothing, and it talks
to a real model on a credential of your own, so every run costs whatever that credential
is billed at, twenty-five questions at a time.

```bash
uv run poe demo claude_complex_query --scripted        # the whole sweep, unattended
uv run poe demo claude_complex_query --list            # what it asks, without asking
uv run poe demo claude_complex_query --only quest_detail --only multi_hop
uv run poe demo claude_complex_query --scripted --log runs/sweep.log
```

Answers from `data`, the real artifact, since the point is breadth and the test fixture
holds 28 entities.

## Asking you back

Four tools reach the person who asked, and the model is told they are the only way to
get anything from them:

| tool | for |
|---|---|
| `ask_to_clarify` | the question is too vague to look anything up for |
| `ask_to_confirm` | a reading has been settled on that could be wrong |
| `ask_to_choose` | several things answer to one name, or a lookup came back unknown |
| `ask_for_more` | another page is about to be spent on a long answer |


Typed at, you answer them yourself. With `--scripted` each probe supplies its own
replies, so a whole sweep runs unattended and always the same way.

## What it reports

Per probe: every tool call with its arguments, the final answer, and a line per
expectation: whether it read the wiki at all, whether it read it in as many different
ways as the question needs, whether it turned back to you when it had to, and whether
the answer carries the words only the wiki could have supplied.

## Keeping a run

`--log FILE` writes everything the run prints to that file as well as to the terminal,
replacing whatever was there before and creating the directory if it has to. Both
streams are copied, so a run that fails leaves the reason in the file, and a question
the model asked is logged with the answer typed back at it.

## What it cannot ask

- **proximity**, "what is within twenty tiles of Lumbridge Castle?" The tiles are in
  the artifact, but no tool takes a coordinate. This will be added in a later update. 

## Setting up

Same two credentials as the other demonstrations here, and neither is shared between
them.

**The wiki key**, read straight from the file `poe keys issue` writes, never from a
`.env`:

```bash
uv run poe keys init                     # once, if you have not already
uv run poe keys issue --label demos      # kept in tokens/demos.json
```

**A `.env` in this folder** (git-ignored) for the Anthropic credential:

```
CLAUDE_CODE_OAUTH_TOKEN=
```

Generate that with `claude setup-token` to bill a Claude subscription, or put an
`ANTHROPIC_API_KEY=` there instead. This script reaches the api itself and cannot borrow
whoever `claude` on this machine is signed in as, so one of the two has to be spelt out.
Any `WIKI_API_` setting in the same file is picked up too.
