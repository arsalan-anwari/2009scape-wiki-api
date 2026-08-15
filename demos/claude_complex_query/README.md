# How much can this wiki actually be asked?

Puts forty-one questions of different shapes to Claude, one per capability rather than
one per tool, and counts what came back. The point is not that any single answer is
right; it is the tally at the end, which says how much of the data model a question can
reach today and which tools nothing thought to call. It verifies nothing, and it talks
to a real model on a credential of your own, so every run costs whatever that credential
is billed at, forty-one questions at a time.

```bash
uv run poe demo claude_complex_query --scripted        # the whole sweep, unattended
uv run poe demo claude_complex_query --list            # what it asks, without asking
uv run poe demo claude_complex_query --only quest_detail --only multi_hop
uv run poe demo claude_complex_query --scripted --report runs/sweep.md
```

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

## Watching one run

Every call is kept at the moment it is made, then how long the probe took and how many
steps it spent, so a probe that has stopped and a probe still thinking do not read the
same. Nothing here can wait indefinitely either: the model is given two minutes to
answer one turn and a probe ten minutes to finish, after which it is given up on, the
steps it did reach are kept along with the reason it stopped, and the sweep carries on
with the questions it has not put yet.

If a probe does stall, re-run that one on its own and the last call it made is the one
it stopped on:

```bash
uv run poe demo claude_complex_query --scripted --only reverse_skilling
```

## Keeping a run

`--report FILE` writes the run to that file as a markdown document, replacing whatever
was there before and creating the directory if it has to.

```text
  ✅ manifest                2 steps      8s   passed
  ⚠️ npc_stats               9 steps     52s   fell short
  [ 3/36] item_value  14s  ✅ 1  ⚠️ 1  ❌ 0  elapsed 1m 14s
```

## What it does yet tests

- **proximity**, "what is within twenty tiles of Lumbridge Castle?" The tiles are in
  the artifact, but no tool takes a coordinate. This will be added in a later update.
- **the largest of the things sharing one name**, "which Bank booth has the most of
  itself standing in the world?" Comparing by a number goes through a whole sort and
  takes no name, so answering it means fetching each namesake in turn.

## Setting up

One credential, the same as the other demonstrations here and shared with none of them:
**a `.env` in this folder** (git-ignored) for the Anthropic credential.

```
CLAUDE_CODE_OAUTH_TOKEN=
```

Generate that with `claude setup-token` to bill a Claude subscription, or put an
`ANTHROPIC_API_KEY=` there instead. This script reaches the api itself and cannot borrow
whoever `claude` on this machine is signed in as, so one of the two has to be spelt out.
Nothing else belongs in that file: the wiki is a process this run starts for itself.
