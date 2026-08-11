"""Every question this demonstration puts, and what an answer that used
the wiki holds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Probe:
    """One question, what it is here to prove, and how to tell whether it did."""

    tag: str
    covers: str
    question: str
    reaches: int = 1
    says: tuple[str, ...] = ()
    says_any: tuple[str, ...] = ()
    answers: tuple[str, ...] = ()
    human_turn: bool = False


#: The sweep, in the order it runs. Every entity type and every link this build holds
#: is reached by at least one of these.
PROBES: tuple[Probe, ...] = (
    Probe(
        tag="manifest",
        reaches=2,
        covers="the written surface: what this build is and what sorts it holds",
        question=(
            "What is this wiki built from, and what sorts of thing does it know about? "
            "Give me the data version and the two largest sorts by count."
        ),
        says=("item",),
    ),
    Probe(
        tag="browse_rooms",
        reaches=1,
        covers="listing a whole sort, and construction room attributes",
        question=(
            "List the construction rooms this game has and tell me which is the most "
            "expensive to build, with its cost and the Construction level it needs."
        ),
        says=("Treasure room",),
    ),
    Probe(
        tag="item_value",
        reaches=1,
        covers="item attributes: market price, price confidence and equipment bonuses",
        question=(
            "How much is Statius's warhammer worth on the market, how much can I "
            "trust that price, and what does it do for my strength?"
        ),
        says=("traded",),
    ),
    Probe(
        tag="npc_stats",
        reaches=1,
        covers="npc combat attributes, and a name eighteen things answer to",
        question="How dangerous is a Tormented demon? Give me its combat stats.",
        says=("326",),
        answers=("the strongest one you have",),
        human_turn=True,
    ),
    Probe(
        tag="scenery_use",
        reaches=1,
        covers="scenery as an entity type, with the options the game gives it",
        question="What can I do with a Bank booth, and how many are in the world?",
        says=("Collect",),
        answers=("whichever has the most placements",),
    ),
    Probe(
        tag="quest_detail",
        reaches=2,
        covers="quest attributes authored by hand, and what a quest asks you to bring",
        question=(
            "How hard is Desert Treasure, how long does it take, what series is it "
            "part of, which skills does it want, and what must I bring with me?"
        ),
        says=("master", "Mahjarrat"),
    ),
    Probe(
        tag="slayer_task",
        reaches=1,
        covers="the task entity type and the advice it carries",
        question=(
            "What Slayer level do I need before I can be sent after Skeletal wyverns, "
            "and what does the game warn me about them?"
        ),
        says=("72",),
    ),
    Probe(
        tag="shop_currency",
        reaches=1,
        covers="a pointer attribute resolving to a named thing rather than an id",
        question="What does Tzhaar-mej-roh's Rune Store take as payment?",
        says=("Tokkul",),
    ),
    Probe(
        tag="place_hierarchy",
        reaches=3,
        covers="locations, their tiles, and the part_of / contains pair",
        question=(
            "Where is Draynor Manor on the map, what larger place is it part of, and "
            "what does Burthorpe contain?"
        ),
        says=("Draynor Village", "Heroes' Guild"),
    ),
    Probe(
        tag="drops_paged",
        reaches=1,
        covers="a drop table too long for one answer, so the reader is asked first",
        question=(
            "What does the King Black Dragon drop? There are a lot, so show me the "
            "first few and check with me before reading the rest."
        ),
        says=("Dragon bones",),
        answers=("yes, show me the rest", "that is enough"),
        human_turn=True,
    ),
    Probe(
        tag="who_drops_it",
        reaches=1,
        covers="following a link backwards, from an item to everything that drops it",
        question="Which monsters drop Dragon bones?",
        says=("dragon",),
    ),
    Probe(
        tag="what_wants_it",
        reaches=1,
        covers="the requires / needed_for pair, which the quest overlays feed",
        question=(
            "Which quest wants me to bring an Iron chainbody, and what else does "
            "that quest ask for?"
        ),
        says=("Black Knights",),
    ),
    Probe(
        tag="shop_lines",
        reaches=2,
        covers="shops from both ends, with price and who stands behind the counter",
        question=(
            "Where can I buy Iron arrowtips and for how much, and who runs the shop "
            "you find them in?"
        ),
        says=("Ava",),
    ),
    Probe(
        tag="slayer_chain",
        reaches=2,
        covers="assigns / assigned_by and satisfied_by, the two slayer links",
        question=(
            "Which Slayer masters can assign Aberrant spectres, and what creatures "
            "count towards a Steel dragons task?"
        ),
        says=("Vannaka", "Steel dragon"),
    ),
    Probe(
        tag="skilling",
        reaches=2,
        covers="yields and makes: gathering a resource and turning it into something",
        question=(
            "What can I catch at a fishing spot and at what levels, and what do raw "
            "shrimps turn into when I cook them?"
        ),
        says=("Shrimps",),
    ),
    Probe(
        tag="ammunition",
        reaches=2,
        covers="the uses_ammunition pair, followed both ways between two items",
        question=(
            "What ammunition does a Phoenix crossbow take, and which other weapons "
            "fire Bronze bolts?"
        ),
        says=("bolts",),
    ),
    Probe(
        tag="spawns",
        reaches=2,
        covers="located_in both ways: what lies in a place, and where a thing lies",
        question=(
            "What items lie on the ground in the Clocktower, and whereabouts does a "
            "White cog spawn?"
        ),
        says=("cog",),
    ),
    Probe(
        tag="reverse_skilling",
        reaches=2,
        covers="gathered_from and made_from, the two skilling links read backwards",
        question=(
            "Where do Raw salmon come from, and what are Shrimps made from and with "
            "which skill?"
        ),
        says=("cooking",),
    ),
    Probe(
        tag="shop_from_npc",
        reaches=2,
        covers="runs_shop and sells, a shop reached from the person behind the counter",
        question="Which shop does Ava run, and what does it stock?",
        says=("arrowtips",),
    ),
    Probe(
        tag="master_tasks",
        reaches=2,
        covers="assigns and counts_towards, the slayer links read the other way",
        question=(
            "What can Vannaka send me after, and which Slayer tasks does killing a "
            "Steel dragon count towards?"
        ),
        says=("Steel dragon",),
    ),
    Probe(
        tag="search_words",
        reaches=1,
        covers="full text search over names and descriptions, rather than a lookup",
        question=(
            "Search this wiki for anything with 'dragonfire' in it and tell me how "
            "many there are."
        ),
    ),
    Probe(
        tag="multi_hop",
        reaches=3,
        covers="three links in a row, which no single tool answers",
        question=(
            "I want a Slayer task that will earn me dragon bones. Work out which "
            "creatures drop them, which of those are a Slayer task, and which master "
            "hands that task out."
        ),
        says=("dragon",),
    ),
    Probe(
        tag="fuzzy_name",
        reaches=2,
        covers="a misspelt name settled by asking rather than by guessing",
        question="tell me about the abysal wipe",
        says=("Abyssal whip",),
        answers=("item", "Abyssal whip"),
        human_turn=True,
    ),
    Probe(
        tag="vague_question",
        reaches=0,
        covers="a question too vague to look anything up for, so it must be narrowed",
        question="what is the best weapon?",
        says=(),
        answers=("best for melee, at attack level 70",),
        human_turn=True,
    ),
    Probe(
        tag="honest_gap",
        reaches=1,
        covers="a fact this build lacks, which should be said rather than invented",
        question="What does completing Desert Treasure reward you with?",
        says_any=("no", "not", "cannot", "does not", "nothing"),
    ),
    Probe(
        tag="filter_by_attribute",
        reaches=1,
        covers="picking things out by a number rather than by name",
        question=(
            "Which weapons give more than 100 strength bonus? Name them and say "
            "how much each one gives."
        ),
        says=("godsword",),
    ),
    Probe(
        tag="order_by_attribute",
        reaches=1,
        covers="asking for the cheapest or largest of something",
        question=(
            "What is the cheapest food that restores more than 10 hitpoints, and "
            "how much does it restore?"
        ),
        says_any=("batta", "legs", "hole", "toad"),
    ),
    Probe(
        tag="price_over_time",
        reaches=1,
        covers="how a price moved, rather than what it is now",
        question=(
            "Has the Abyssal whip gone up or down over the last year, and by how much?"
        ),
        says_any=("up", "down", "fell", "rose"),
    ),
)


# Questions this surface cannot answer today, and what each waits on.
#
# Probe(
#     tag="nearby",
#     covers="what is close to somewhere on the map",
#     question="What is within twenty tiles of Lumbridge Castle?",
# ),
#   Waits on scenery carrying a tile: without one the answer would name items and
#   creatures and leave out every bank, altar and tree.
