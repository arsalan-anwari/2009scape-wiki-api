"""Every question this demonstration puts, and what an answer that used
the wiki holds."""

from __future__ import annotations

from dataclasses import dataclass, field

from wiki_api.core import Direction
from wiki_api.domain.relationships import RELATIONSHIP_SPECS, RelationshipType
from wiki_api.surfaces.mcp import CLOSE_NAMES_TOOL
from wiki_api.surfaces.mcp.naming import tool_name


def following(rel: RelationshipType, direction: Direction) -> str:
    """Name the tool that follows one link one way round, off the registry rather than
    written down here, so a link renamed there is renamed here too.
    """
    return tool_name(RELATIONSHIP_SPECS[rel], direction)


MORE = "ask_for_more"
CHOOSE = "ask_to_choose"
CONFIRM = "ask_to_confirm"
CLARIFY = "ask_to_clarify"
DENIALS: tuple[str, ...] = (
    "does not hold",
    "doesn't hold",
    "no record",
    "not recorded",
    "holds nothing",
    "nothing on",
    "no combat",
    "cannot tell you",
    "can't tell you",
)


@dataclass(frozen=True)
class Probe:
    """One question, what it is here to prove, and how to tell whether it did."""

    tag: str
    covers: str
    question: str
    reaches: int = 1
    calls: tuple[str, ...] = ()
    says: tuple[str, ...] = ()
    says_any: tuple[str, ...] = ()
    never_says: tuple[str, ...] = ()
    answers: tuple[str, ...] = ()
    human_turn: bool = False
    may_ask: tuple[str, ...] = field(default=(MORE,))


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
        says=("traded", "114"),
        never_says=DENIALS,
    ),
    Probe(
        tag="npc_stats",
        reaches=1,
        covers="npc combat attributes, under a name eighteen records used to answer to",
        question="How dangerous is a Tormented demon? Give me its combat stats.",
        says=("326", "85"),
        never_says=DENIALS,
    ),
    Probe(
        tag="scenery_use",
        reaches=1,
        covers="scenery as an entity type, with the options the game gives it",
        question="What can I do with a Bank booth, and how many are in the world?",
        says=("Collect", "96"),
        may_ask=(MORE,),
    ),
    Probe(
        tag="quest_detail",
        reaches=2,
        covers="quest attributes authored by hand, and what a quest asks you to bring",
        question=(
            "How hard is Desert Treasure, how long does it take, what series is it "
            "part of, which skills does it want, and what must I bring with me?"
        ),
        says=("master", "Mahjarrat", "thieving"),
    ),
    Probe(
        tag="slayer_task",
        reaches=1,
        covers="the task entity type and the advice it carries",
        question=(
            "What Slayer level do I need before I can be sent after Skeletal wyverns, "
            "and what does the game warn me about them?"
        ),
        says=("72", "elemental"),
        never_says=DENIALS,
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
        reaches=1,
        covers="a place described by what it is and what it sits inside, not by tiles",
        question=(
            "Tell me about Draynor Manor: what sort of place is it, and what larger "
            "place is it part of?"
        ),
        says=("Draynor Village",),
        never_says=DENIALS,
    ),
    Probe(
        tag="place_contents",
        reaches=2,
        covers="the part_of / contains pair, a place read from both ends",
        question=(
            "List every place recorded inside Varrock, the whole list rather than a "
            "few examples, and tell me which larger place White Knights' Castle "
            "belongs to."
        ),
        calls=(
            following(RelationshipType.PART_OF, Direction.REVERSE),
            following(RelationshipType.PART_OF, Direction.FORWARD),
        ),
        says=("Varrock Square", "Falador"),
        never_says=DENIALS,
    ),
    Probe(
        tag="music_track",
        reaches=1,
        covers="music as an entity type, with the set and the sentence it carries",
        question=(
            "Tell me about the music track Adventure: which set is it part of, and "
            "how is it unlocked?"
        ),
        says=("Varrock Palace",),
    ),
    Probe(
        tag="music_place",
        reaches=2,
        covers="located_in with music at one end, from the track and from the place",
        question="Where is the track Fanfare heard, and what does Varrock Palace hold?",
        says=("Falador", "Adventure"),
    ),
    Probe(
        tag="quest_music",
        reaches=2,
        covers="heard_during and music_heard, the newest link read both ways",
        question=(
            "Which pieces of music play during Dream Mentor, and which quest is the "
            "track Suspicious heard during?"
        ),
        says=("Monkey Madness", "Everlasting"),
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
        tag="rare_drops",
        reaches=1,
        covers="a roll on a table many monsters share, read as the items it gives",
        question=(
            "Does the King Black Dragon drop a Draconic visage, and roughly how often? "
            "Name two of the rarest things it can drop besides that."
        ),
        says=("Draconic visage",),
        never_says=DENIALS,
    ),
    Probe(
        tag="unplayable_quest",
        reaches=1,
        covers="a quest the game declares but no class implements",
        question="Is the quest Monkey Madness available in the game?",
        says_any=("not implemented", "cannot", "can't", "no"),
        may_ask=(MORE, CHOOSE),
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
        tag="narrowed_walk",
        reaches=1,
        covers="a link answering with several sorts, narrowed to one of them",
        question=(
            "Animal Magnetism needs other quests finished and items carried. Ignore "
            "the quests: which items does it ask me to bring, and how many are there?"
        ),
        says=("3",),
        never_says=DENIALS,
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
        may_ask=(MORE, CHOOSE),
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
            "How many fishing spots are there in the game, what can I catch at one "
            "and at what levels, and what do raw shrimps turn into when cooked?"
        ),
        says=("Shrimps",),
        may_ask=(MORE,),
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
        may_ask=(MORE, CHOOSE),
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
        tag="smithing_bar",
        reaches=1,
        covers="makes, from one ingredient to everything the game turns it into",
        question=(
            "I have a Bronze bar. What can I smith from it, and what Smithing level "
            "does each one need? Give me the cheapest handful."
        ),
        calls=(following(RelationshipType.MAKES, Direction.FORWARD),),
        says=("Bronze dagger",),
        may_ask=(MORE, CONFIRM, CHOOSE),
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
        tag="music_chain",
        reaches=2,
        covers="a quest, the music it unlocks, and where in the world that music plays",
        question=(
            "If I finish The Fremennik Isles, which music does it unlock, and "
            "whereabouts in the world do those tracks play?"
        ),
        says=("Volcanic Vikings", "Neitiznot"),
    ),
    Probe(
        tag="fuzzy_name",
        reaches=2,
        covers="a misspelt name settled by asking rather than by guessing",
        question="tell me about the abysal wipe",
        says=("Abyssal whip",),
        answers=("an item, yes", "Abyssal whip"),
        human_turn=True,
        may_ask=(MORE, CHOOSE, CONFIRM, CLARIFY),
    ),
    Probe(
        tag="bad_spelling",
        reaches=2,
        covers="a name too badly spelt to search for, put back to whoever asked",
        question="whats the drangon scimatar worth",
        calls=(CLOSE_NAMES_TOOL,),
        says=("Dragon scimitar",),
        answers=("an item, yes", "Dragon scimitar"),
        human_turn=True,
        may_ask=(MORE, CHOOSE, CONFIRM, CLARIFY),
    ),
    Probe(
        tag="music_name",
        reaches=1,
        covers="one name held by two sorts of thing, told apart by what the asker said",
        question="Where is the music track Monkey Madness unlocked in the game?",
        says=("Ape Atoll", "Jungle"),
        may_ask=(),
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
        covers="what a quest gives you, which only a community guide ever wrote down",
        question="What does completing Desert Treasure reward you with?",
        says=("Ancient Magicks",),
        never_says=DENIALS,
    ),
    Probe(
        tag="music_gap",
        reaches=1,
        covers="a track unlocked by content this build holds no entity for",
        question="Which quest do I have to finish to unlock the track Melodrama?",
        says=("Castle Wars",),
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
        reaches=2,
        covers="ordering by a number, then pricing the answer over a shop counter",
        question=(
            "Which foods restore more than 15 hitpoints? Of those, which is the "
            "cheapest to buy over a shop counter, which shop sells it, and what does "
            "that shop charge for it?"
        ),
        calls=(following(RelationshipType.SELLS, Direction.REVERSE),),
        says=("Tuna potato", "Delicious Goods", "113"),
        never_says=DENIALS,
        may_ask=(MORE, CHOOSE),
    ),
    Probe(
        tag="music_spread",
        reaches=1,
        covers="a number the newest sort of thing records, ordered largest first",
        question=(
            "Which music plays across the most map squares in the world, and how many "
            "does it play in?"
        ),
        says=("Bounty Hunter",),
    ),
    Probe(
        tag="price_over_time",
        reaches=1,
        covers="how a price moved, rather than what it is now",
        question=(
            "Has the Abyssal whip gone up or down over the last year, and by how much?"
        ),
        says_any=("up", "down", "fell", "rose"),
        may_ask=(MORE, CHOOSE),
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
