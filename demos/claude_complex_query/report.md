# Complex query sweep

*Questions of every shape this wiki can be asked, put to one model, with everything it read and everything it said.*

`2026-08-14 16:38`

|  |  |
| --- | --- |
| **model** | `claude-opus-5` |
| **dataset** | `data/knowledge.sqlite3` |
| **wiki** | 32 tools, keyed to `demos` |
| **probes** | 36 |
| **answers** | scripted |

## At a glance

**32 of 36** probes showed everything asked of them, in 9m 07s.

Fell short: `npc_stats`, `scenery_use`, `drops_paged`, `music_name`.

|  | probe | steps | took | what it covers |
| :-: | --- | --: | --: | --- |
| ✅ | [manifest](#manifest) | 2 | 7s | the written surface: what this build is and what sorts it holds |
| ✅ | [browse_rooms](#browse_rooms) | 5 | 18s | listing a whole sort, and construction room attributes |
| ✅ | [item_value](#item_value) | 2 | 8s | item attributes: market price, price confidence and equipment bonuses |
| ⚠️ | [npc_stats](#npc_stats) | 3 | 14s | npc combat attributes, and a name eighteen things answer to |
| ⚠️ | [scenery_use](#scenery_use) | 28 | 40s | scenery as an entity type, with the options the game gives it |
| ✅ | [quest_detail](#quest_detail) | 2 | 10s | quest attributes authored by hand, and what a quest asks you to bring |
| ✅ | [slayer_task](#slayer_task) | 2 | 9s | the task entity type and the advice it carries |
| ✅ | [shop_currency](#shop_currency) | 1 | 6s | a pointer attribute resolving to a named thing rather than an id |
| ✅ | [place_hierarchy](#place_hierarchy) | 2 | 7s | locations, their tiles, and the part_of / contains pair |
| ✅ | [music_track](#music_track) | 1 | 6s | music as an entity type, with the set and the sentence it carries |
| ✅ | [music_place](#music_place) | 4 | 11s | located_in with music at one end, from the track and from the place |
| ✅ | [quest_music](#quest_music) | 2 | 6s | heard_during and music_heard, the newest link read both ways |
| ⚠️ | [drops_paged](#drops_paged) | 5 | 19s | a drop table too long for one answer, so the reader is asked first |
| ✅ | [who_drops_it](#who_drops_it) | 5 | 16s | following a link backwards, from an item to everything that drops it |
| ✅ | [what_wants_it](#what_wants_it) | 2 | 8s | the requires / needed_for pair, which the quest overlays feed |
| ✅ | [narrowed_walk](#narrowed_walk) | 1 | 5s | a link answering with several sorts, narrowed to one of them |
| ✅ | [shop_lines](#shop_lines) | 4 | 9s | shops from both ends, with price and who stands behind the counter |
| ✅ | [slayer_chain](#slayer_chain) | 2 | 7s | assigns / assigned_by and satisfied_by, the two slayer links |
| ✅ | [skilling](#skilling) | 10 | 34s | yields and makes: gathering a resource and turning it into something |
| ✅ | [ammunition](#ammunition) | 6 | 18s | the uses_ammunition pair, followed both ways between two items |
| ✅ | [spawns](#spawns) | 4 | 10s | located_in both ways: what lies in a place, and where a thing lies |
| ✅ | [reverse_skilling](#reverse_skilling) | 4 | 17s | gathered_from and made_from, the two skilling links read backwards |
| ✅ | [shop_from_npc](#shop_from_npc) | 3 | 11s | runs_shop and sells, a shop reached from the person behind the counter |
| ✅ | [master_tasks](#master_tasks) | 10 | 38s | assigns and counts_towards, the slayer links read the other way |
| ✅ | [search_words](#search_words) | 1 | 9s | full text search over names and descriptions, rather than a lookup |
| ✅ | [multi_hop](#multi_hop) | 25 | 35s | three links in a row, which no single tool answers |
| ✅ | [music_chain](#music_chain) | 11 | 16s | a quest, the music it unlocks, and where in the world that music plays |
| ✅ | [fuzzy_name](#fuzzy_name) | 7 | 27s | a misspelt name settled by asking rather than by guessing |
| ⚠️ | [music_name](#music_name) | 1 | 7s | one name held by two sorts of thing, settled by asking which was meant |
| ✅ | [vague_question](#vague_question) | 10 | 45s | a question too vague to look anything up for, so it must be narrowed |
| ✅ | [honest_gap](#honest_gap) | 2 | 11s | a fact this build lacks, which should be said rather than invented |
| ✅ | [music_gap](#music_gap) | 2 | 9s | a track unlocked by content this build holds no entity for |
| ✅ | [filter_by_attribute](#filter_by_attribute) | 3 | 14s | picking things out by a number rather than by name |
| ✅ | [order_by_attribute](#order_by_attribute) | 3 | 14s | asking for the cheapest or largest of something |
| ✅ | [music_spread](#music_spread) | 4 | 11s | a number the newest sort of thing records, ordered largest first |
| ✅ | [price_over_time](#price_over_time) | 2 | 12s | how a price moved, rather than what it is now |

<sub>✅ showed everything asked of it, ⚠️ fell short of something, ❌ came apart, or said the wiki holds nothing where it does</sub>

### Tool coverage

**28 of 32** tools the wiki offers were called at least once.

Never called by any probe: `contains`, `find_close_names`, `makes`, `part_of`.

### Turns back to you

| tool | times |
| --- | --: |
| `ask_for_more` | 7 |
| `ask_to_choose` | 4 |
| `ask_to_clarify` | 1 |
| `ask_to_confirm` | 2 |

---

## manifest

*the written surface: what this build is and what sorts it holds*

✅ **passed** in 7s over 2 step(s)

> **Asked** What is this wiki built from, and what sorts of thing does it know about? Give me the data version and the two largest sorts by count.

**What it did**

> *I'll check the build info and the sorts breakdown.*

```text
about()
list_sorts()
```

**What it said**

````markdown
The wiki is built from the 2009scape game data, data version **2026.08.14.092403** (schema 9, built 2026-08-14, from game commit `91bb6be1`).

It knows about nine sorts of thing: items, NPCs, shops, quests, locations, scenery objects, slayer tasks, house rooms and music tracks. The two largest by count are **scenery objects (9,139)** and **items (8,578)** — with NPCs close behind at 7,995.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'item' |

<sub>[back to the table](#at-a-glance)</sub>

---

## browse_rooms

*listing a whole sort, and construction room attributes*

✅ **passed** in 18s over 5 step(s)

> **Asked** List the construction rooms this game has and tell me which is the most expensive to build, with its cost and the Construction level it needs.

**What it did**

> *I'll look up the construction rooms in the knowledge base.*

```text
list_things(type='room', limit=50)
compare_by_number(type='room', ordered_by='cost', descending=True, limit=5)
compare_by_number(type='room', ordered_by='cost', descending=True)
compare_by_number(type='room', ordered_by='Build cost', descending=True)
get_thing(name='Treasure room', type='room')
```

**What it said**

````markdown
The wiki lists **27** construction rooms:

Parlour, Garden, Kitchen, Dining room, Workshop, Bedroom, Skill hall, Games room, Combat room, Quest hall, Study room, Costume room, Chapel, Portal chamber, Formal garden, Throne room, Oubilette, Dungeon corridor, Dungeon junction, Dungeon stairs, Dungeon pit, Treasure room, Roof 2 exit, Roof 3 exit, Roof 4 exit, Skill hall 2, Quest hall 2.

The most expensive is the **Treasure room** at **250,000 gp**, requiring **Construction level 75** (12 build spots). Next are the Oubilette and Throne room at 150,000 each, then the Portal chamber at 100,000.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 5 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'Treasure room' |

<sub>[back to the table](#at-a-glance)</sub>

---

## item_value

*item attributes: market price, price confidence and equipment bonuses*

✅ **passed** in 8s over 2 step(s)

> **Asked** How much is Statius's warhammer worth on the market, how much can I trust that price, and what does it do for my strength?

**What it did**

> *I'll look up the warhammer's details and price history.*

```text
get_thing(name="Statius's warhammer", type='item')
how_the_price_moved(name="Statius's warhammer")
```

**What it said**

````markdown
Statius's warhammer sits at **6,893,037 gp**, and the wiki rates that price as **"traded"** — genuine market activity, based on 113 snapshots, so it's a figure you can lean on. It has climbed from 6,540,000 on 2024-06-08 to 6,893,037 on 2026-08-01, up 353,037 (+5.4%), ranging between 6,200,000 and 6,973,417 with a median of 6,583,712.

For strength it gives a **+114 strength bonus**, alongside +123 crush attack (but -4 stab and -4 slash). It needs 78 Attack, swings at 6 ticks, has a special attack, and degrades in combat until it turns to dust.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'traded' |
| ✅ | the answer carries '114' |

<sub>[back to the table](#at-a-glance)</sub>

---

## npc_stats

*npc combat attributes, and a name eighteen things answer to*

⚠️ **fell short** in 14s over 3 step(s)

> **Asked** How dangerous is a Tormented demon? Give me its combat stats.

**What it did**

```text
search(words='Tormented demon', type='npc')
get_thing(name='npc:8349', type='npc')
get_thing(name='npc:8358', type='npc')
```

**What it said**

````markdown
The wiki lists 18 Tormented demon NPC IDs, but the ones I checked (8349 and 8358) are identical, so these stats should hold across the set:

- **Lifepoints:** 326; all combat levels 85 (Attack, Strength, Defence, Magic, Ranged); attack speed 6 ticks
- **Attack bonuses:** Stab 112, Slash 132, Crush 113, Magic 111, Ranged 245
- **Defence bonuses:** Stab 167, Slash 394, Crush 346, Magic 213, Ranged 349, Summoning 167
- **Other bonuses:** Strength 65, Prayer 39, Magic damage 65, Ranged strength 58

Danger-wise: it's aggressive, immune to poison, roams up to 40 tiles, attacks with magic and uses a melee protection prayer — but it is safespottable. It gives 136 Slayer experience and respawns after 100 ticks, with 33 possible drops recorded.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 2 different ways |
| ❌ | it settled the question itself instead of asking |
| ✅ | the answer carries '326' |
| ✅ | the answer carries '85' |

<sub>[back to the table](#at-a-glance)</sub>

---

## scenery_use

*scenery as an entity type, with the options the game gives it*

⚠️ **fell short** in 40s over 28 step(s)

> **Asked** What can I do with a Bank booth, and how many are in the world?

**What it did**

```text
get_thing(name='Bank booth', type='scenery')
search(words='Bank booth', type='scenery')
```

> **It asked you** (`ask_to_confirm`)
>
> The wiki holds several separate scenery entries all called "Bank booth" (32 matches on that name). Which should I count?
>
> - proposing: I'll treat "Bank booth" as all of the entries with that name and add up their world counts, rather than reporting just the first one (ID 2213, which has 16 standing in the world and the actions Use, Use-quickly, Collect).
>
> **You answered** *the probe's own answer*
>
> whichever has the most placements

```text
search(words='Bank booth', type='scenery', offset=10)
search(words='Bank booth', type='scenery', offset=20)
search(words='Bank booth', type='scenery', offset=30)
get_thing(name='scenery:14367')
get_thing(name='scenery:14368')
get_thing(name='scenery:16700')
get_thing(name='scenery:22819')
get_thing(name='scenery:24914')
get_thing(name='scenery:26972')
get_thing(name='scenery:29085')
get_thing(name='scenery:30015')
get_thing(name='scenery:34752')
get_thing(name='scenery:35647')
get_thing(name='scenery:35648')
get_thing(name='scenery:36262')
get_thing(name='scenery:11402')
get_thing(name='scenery:2214')
get_thing(name='scenery:34205')
get_thing(name='scenery:3045')
get_thing(name='scenery:5276')
get_thing(name='scenery:6084')
get_thing(name='scenery:10517')
get_thing(name='scenery:11338')
get_thing(name='scenery:11758')
get_thing(name='scenery:36786')
```

**What it said**

````markdown
The Bank booth with the most placements is the one I first looked up, **ID 2213** ("The bank teller will serve you from here"): 16 standing in the world, more than any other of the 23 scenery entries by that name (next highest are 6 each, for IDs 11402 in Varrock, 11758 in Falador/Park, 22819 and 24914 in Canifis).

Its actions are **Use, Use-quickly and Collect** — so banking, quick-banking, and collecting from the item collection box. It's not members-only, occupies 1×1 tiles, and appears in 5 locations, including Catherby, Tree Gnome Stronghold and the Fishing Guild.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 27 time(s) |
| ✅ | it read the wiki 2 different ways |
| ⚠️ | it asked when it did not have to: ask_to_confirm |
| ✅ | the answer carries 'Collect' |

<sub>[back to the table](#at-a-glance)</sub>

---

## quest_detail

*quest attributes authored by hand, and what a quest asks you to bring*

✅ **passed** in 10s over 2 step(s)

> **Asked** How hard is Desert Treasure, how long does it take, what series is it part of, which skills does it want, and what must I bring with me?

**What it did**

> *I'll look up the quest details.*

```text
get_thing(name='Desert Treasure', type='quest')
requires(name='Desert Treasure')
```

**What it said**

````markdown
**Desert Treasure** is rated **master** difficulty, **long** length, worth **3 quest points**, and is members-only. It's part of the **Mahjarrat** series.

Skills needed: **Firemaking 50, Magic 50, Slayer 10, Thieving 53**. It also requires six completed quests: The Dig Site, The Tourist Trap, Temple of Ikov, Priest in Peril, Waterfall Quest, and Troll Stronghold.

On what to bring: the wiki entry lists no required items for this quest — all six of its recorded requirements are the quests above, so I can't tell you an item list from this data.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'master' |
| ✅ | the answer carries 'Mahjarrat' |
| ✅ | the answer carries 'thieving' |

<sub>[back to the table](#at-a-glance)</sub>

---

## slayer_task

*the task entity type and the advice it carries*

✅ **passed** in 9s over 2 step(s)

> **Asked** What Slayer level do I need before I can be sent after Skeletal wyverns, and what does the game warn me about them?

**What it did**

> *I'll look that up.*

```text
search(words='Skeletal wyvern')
get_thing(name='Skeletal wyvern', type='task')
```

**What it said**

````markdown
You need **72 Slayer** (and combat level 70) to be assigned Skeletal wyverns, and only **Duradel** hands out the task.

The wiki's advice: they're extremely dangerous and hard to hit with arrows, as those slip right through them — to stand a good chance of surviving you'll need some elemental shielding from their icy breath.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries '72' |
| ✅ | the answer carries 'elemental' |

<sub>[back to the table](#at-a-glance)</sub>

---

## shop_currency

*a pointer attribute resolving to a named thing rather than an id*

✅ **passed** in 6s over 1 step(s)

> **Asked** What does Tzhaar-mej-roh's Rune Store take as payment?

**What it did**

> *I'll look up that shop.*

```text
get_thing(name="Tzhaar-mej-roh's Rune Store", type='shop')
```

**What it said**

````markdown
Tzhaar-mej-roh's Rune Store takes **Tokkul** as its currency. It's not a general store, it doesn't buy alchemy products, it stocks 8 items (fire, water, earth runes among them), and it's staffed by TzHaar-Mej-Roh.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Tokkul' |

<sub>[back to the table](#at-a-glance)</sub>

---

## place_hierarchy

*locations, their tiles, and the part_of / contains pair*

✅ **passed** in 7s over 2 step(s)

> **Asked** Where is Draynor Manor on the map, what larger place is it part of, and what does Burthorpe contain?

**What it did**

> *I'll look up each of these.*

```text
get_thing(name='Draynor Manor', type='location')
get_thing(name='Burthorpe', type='location')
```

**What it said**

````markdown
**Draynor Manor** — a building, "the haunted manor north of Draynor Village," centred at x 3108, y 3345, plane 0 (region 12340). It is part of **Draynor Village**.

**Burthorpe** — a town on the edge of the troll lands, centred at x 2895, y 3549, plane 0 (region 11575). It contains one location: the **Heroes' Guild**. (It also has 193 things listed as found there, if you'd like those.)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Draynor Village' |
| ✅ | the answer carries "Heroes' Guild" |
| ✅ | the answer carries '3108' |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_track

*music as an entity type, with the set and the sentence it carries*

✅ **passed** in 6s over 1 step(s)

> **Asked** Tell me about the music track Adventure: which set is it part of, and how is it unlocked?

**What it did**

> *I'll look that up.*

```text
get_thing(name='Adventure', type='music')
```

**What it said**

````markdown
**Adventure** (music track #177) belongs to the **Varrock** music set, and it is unlocked **at Varrock Palace**. It plays in 1 map square, and is recorded as found in the Palace / Varrock Palace locations.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Varrock Palace' |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_place

*located_in with music at one end, from the track and from the place*

✅ **passed** in 11s over 4 step(s)

> **Asked** Where is the track Fanfare heard, and what does Varrock Palace hold?

**What it did**

> *I'll look both up.*

```text
search(words='Fanfare', type='music')
get_thing(name='Varrock Palace', type='location')
found_in(name='music:72')
found_here(name='Varrock Palace')
```

**What it said**

````markdown
**Fanfare** (music, id 72) is heard in 3 locations: Falador, the Park, and White Knights' Castle. (Note the wiki also lists separate tracks named Fanfare2 and Fanfare3, if you meant one of those.)

**Varrock Palace** — King Roald's palace in northern Varrock (centre x 3213, y 3483, plane 0), part of Varrock — holds 3 things: the music track Adventure, and the quests Shield of Arrav and All Fired Up.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 4 different ways |
| ✅ | the answer carries 'Falador' |
| ✅ | the answer carries 'Adventure' |

<sub>[back to the table](#at-a-glance)</sub>

---

## quest_music

*heard_during and music_heard, the newest link read both ways*

✅ **passed** in 6s over 2 step(s)

> **Asked** Which pieces of music play during Dream Mentor, and which quest is the track Suspicious heard during?

**What it did**

> *I'll look up both parts of this.*

```text
music_heard(name='Dream Mentor')
heard_during(name='Suspicious')
```

**What it said**

````markdown
Dream Mentor has six tracks in the wiki: **Everlasting, Illusive, Inadequacy, Untouchable, Down and Out,** and **On the Up**.

The track **Suspicious** is heard during **Monkey Madness** (its only listed quest).
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Monkey Madness' |
| ✅ | the answer carries 'Everlasting' |

<sub>[back to the table](#at-a-glance)</sub>

---

## drops_paged

*a drop table too long for one answer, so the reader is asked first*

⚠️ **fell short** in 19s over 5 step(s)

> **Asked** What does the King Black Dragon drop? There are a lot, so show me the first few and check with me before reading the rest.

**What it did**

> *I'll look up the King Black Dragon's drops.*

```text
drops(name='King Black Dragon')
```

> **It asked you** (`ask_for_more`)
>
> Here are the first 10 of the King Black Dragon's 34 drops: Dwarf remains (1/1), Dragon bones (1/1), Black dragonhide (1/1), Crimson charm (1/2), Dwarf remains (1/4), Dwarf remains (1/5), Fire rune (1/20), Air rune (1/20), Coins (1/20), Adamant platebody (1/20). Shall I read on to the remaining 24?
>
> - shown 10 of 34
>
> **You answered** *the probe's own answer*
>
> yes, show me the rest

```text
drops(name='King Black Dragon', offset=10)
drops(name='King Black Dragon', offset=20)
drops(name='King Black Dragon', offset=30)
```

**What it said**

````markdown
Here are the remaining 24 of the 34 drops:

**1/20:** Rune longsword, Mithril 2h sword, Adamant 2h sword, Adamant axe, Mithril battleaxe, Amulet of strength, Rune bolts
**Charms:** Gold charm 1/22, Green charm 1/24, Blue charm 1/72
**1/41:** Shark, Oyster, Iron ore, Death rune, Law rune, Blood rune, Iron arrow, Yew logs, Adamantite bar, Runite limbs
**Rarer:** RDT Slot 1/102, Granite lobster pouch 1/102, Kbd heads 1/128, Draconic visage 1/5000
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | it turned back to ask: ask_for_more |
| ⚠️ | the answer never mentions 'Dragon bones' |

<sub>[back to the table](#at-a-glance)</sub>

---

## who_drops_it

*following a link backwards, from an item to everything that drops it*

✅ **passed** in 16s over 5 step(s)

> **Asked** Which monsters drop Dragon bones?

**What it did**

> *I'll look that up.*

```text
dropped_by(name='Dragon bones')
```

> **It asked you** (`ask_for_more`)
>
> 33 monsters drop Dragon bones. The first 10 are: King Black Dragon (x2 variants), Red dragon, Black dragon, Blue dragon, Green dragon, Bronze dragon, Iron dragon, Steel dragon (x2 variants) — all at a 1/1 drop chance. Shall I list the remaining 23?
>
> - shown 10 of 33
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
dropped_by(name='Dragon bones', offset=10)
dropped_by(name='Dragon bones', offset=20)
dropped_by(name='Dragon bones', offset=30)
```

**What it said**

````markdown
All 33 droppers, grouped by name (many are duplicate NPC variants):

- **Always (1/1):** King Black Dragon (2), Red dragon (5), Black dragon (5), Blue dragon (6), Green dragon (5), Bronze dragon, Iron dragon, Steel dragon (2), Brutal green dragon, Mithril dragon
- **1/20:** Dragon impling (2 variants)
- **1/128:** Jogre (2 variants)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'dragon' |

<sub>[back to the table](#at-a-glance)</sub>

---

## what_wants_it

*the requires / needed_for pair, which the quest overlays feed*

✅ **passed** in 8s over 2 step(s)

> **Asked** Which quest wants me to bring an Iron chainbody, and what else does that quest ask for?

**What it did**

```text
needed_for(name='Iron chainbody')
requires(name="Black Knights' Fortress")
```

**What it said**

````markdown
That's **Black Knights' Fortress**, the only quest listing an Iron chainbody. It asks you to carry three items in all: an Iron chainbody, a Bronze med helm, and a Cabbage.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Black Knights' |

<sub>[back to the table](#at-a-glance)</sub>

---

## narrowed_walk

*a link answering with several sorts, narrowed to one of them*

✅ **passed** in 5s over 1 step(s)

> **Asked** Animal Magnetism needs other quests finished and items carried. Ignore the quests: which items does it ask me to bring, and how many are there?

**What it did**

> *I'll look up the quest's item requirements.*

```text
requires(name='Animal Magnetism', type='item')
```

**What it said**

````markdown
Animal Magnetism asks you to bring 3 items: a **mithril axe**, a **hammer**, and an **iron bar** — all listed as carried requirements.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries '3' |

<sub>[back to the table](#at-a-glance)</sub>

---

## shop_lines

*shops from both ends, with price and who stands behind the counter*

✅ **passed** in 9s over 4 step(s)

> **Asked** Where can I buy Iron arrowtips and for how much, and who runs the shop you find them in?

**What it did**

> *I'll look up where Iron arrowtips are sold.*

```text
sold_in(name='Iron arrowtips')
```

> *Three shops sell them. Let me find who runs each.*

```text
staffed_by(name="Dargaud's Bows And Arrows")
staffed_by(name="Ava's Odds and Ends")
staffed_by(name='Void Knight Archery Store')
```

**What it said**

````markdown
Iron arrowtips are sold in three shops, all at the same price of **26 coins** each:

- **Dargaud's Bows And Arrows** — stock 300, run by the **Bow and Arrow salesman**
- **Ava's Odds and Ends** — stock 30, run by **Ava** (with a **Witch** also staffing it)
- **Void Knight Archery Store** — stock 100, run by a **Squire**
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Ava' |

<sub>[back to the table](#at-a-glance)</sub>

---

## slayer_chain

*assigns / assigned_by and satisfied_by, the two slayer links*

✅ **passed** in 7s over 2 step(s)

> **Asked** Which Slayer masters can assign Aberrant spectres, and what creatures count towards a Steel dragons task?

**What it did**

> *I'll look up both of these.*

```text
assigned_by(name='Aberrant spectres')
satisfied_by(name='Steel dragons')
```

**What it said**

````markdown
Aberrant spectres can be assigned by three masters: **Duradel** (weight 7), **Vannaka** (weight 8) and **Chaeldar** (weight 8).

A **Steel dragons** task is satisfied by two NPCs, both named **Steel dragon** (ids 1592 and 3590) — no other creatures count towards it.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Vannaka' |
| ✅ | the answer carries 'Steel dragon' |

<sub>[back to the table](#at-a-glance)</sub>

---

## skilling

*yields and makes: gathering a resource and turning it into something*

✅ **passed** in 34s over 10 step(s)

> **Asked** What can I catch at a fishing spot and at what levels, and what do raw shrimps turn into when I cook them?

**What it did**

```text
search(words='fishing spot')
get_thing(name='Raw shrimps', type='item')
get_thing(name='npc:234')
yields(name='npc:234')
gathered_from(name='Raw shrimps')
yields(name='npc:316')
yields(name='npc:309')
yields(name='npc:312')
yields(name='npc:313')
```

> **It asked you** (`ask_to_choose`)
>
> The wiki has 84 separate "Fishing spot" entries, and each type yields a different set of fish — which kind did you mean? (Cooking answer: raw shrimps become Shrimps.)
>
> - Net/bait spot (npc:316) — shrimps lvl 1, sardine lvl 5, herring lvl 10, anchovies lvl 15
> - Lure/bait river spot (npc:309) — trout lvl 20, pike lvl 25, salmon lvl 30, rainbow fish lvl 38
> - Cage/harpoon spot (npc:312) — tuna lvl 35, lobster lvl 40, swordfish lvl 50
> - Big net/harpoon spot (npc:313) — mackerel & seaweed lvl 16, cod lvl 23, bass lvl 46, shark lvl 76
> - Something else — I'll name the location and you find the spot there
>
> **You answered** *the standing answer, unasked*
>
> the first one, Net/bait spot (npc:316) — shrimps lvl 1, sardine lvl 5, herring lvl 10, anchovies lvl 15

**What it said**

````markdown
At that net/bait spot (npc:316) you can catch four things:

- **Raw shrimps** — level 1, 10 xp, Small fishing net
- **Raw sardine** — level 5, 20 xp, Fishing rod
- **Raw herring** — level 10, 30 xp, Fishing rod
- **Raw anchovies** — level 15, 40 xp, Small fishing net

Cooking raw shrimps makes **Shrimps**.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 9 time(s) |
| ✅ | it read the wiki 4 different ways |
| ✅ | the answer carries 'Shrimps' |

<sub>[back to the table](#at-a-glance)</sub>

---

## ammunition

*the uses_ammunition pair, followed both ways between two items*

✅ **passed** in 18s over 6 step(s)

> **Asked** What ammunition does a Phoenix crossbow take, and which other weapons fire Bronze bolts?

**What it did**

> *I'll look up both parts of this.*

```text
get_thing(name='Phoenix crossbow', type='item')
used_by(name='Bronze bolts')
```

> **It asked you** (`ask_to_choose`)
>
> Three items are named "Phoenix crossbow" in the wiki. Which one do you mean?
>
> - Phoenix crossbow (item 767) — "Second-rate crossbow, former property of the Phoenix Gang."
> - Phoenix crossbow (item 11165)
> - Phoenix crossbow (item 11167)
>
> **You answered** *the standing answer, unasked*
>
> the first one, Phoenix crossbow (item 767) — "Second-rate crossbow, former property of the Phoenix Gang."

> **It asked you** (`ask_for_more`)
>
> 14 weapons fire Bronze bolts; I've read the first 10. Shall I fetch the remaining 4?
>
> - shown 10 of 14
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
uses_ammunition(name='item:767')
used_by(name='Bronze bolts', offset=10)
```

**What it said**

````markdown
The Phoenix crossbow (item 767) takes 6 kinds of ammunition: Bronze bolts, Bronze bolts(p), Bronze bolts(p+), Bronze bolts(p++), Opal bolts and Opal bolts (e).

Bronze bolts are fired by 14 weapons in total. Besides that Phoenix crossbow, they are: Crossbow (837), Bronze crossbow, Blurite crossbow, Iron crossbow, Steel crossbow, Mith crossbow, Adamant crossbow, Rune crossbow (9185 and 13530), Black crossbow, Dorgeshuun c'bow, and the other two Phoenix crossbows (11165 and 11167).
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'bolts' |

<sub>[back to the table](#at-a-glance)</sub>

---

## spawns

*located_in both ways: what lies in a place, and where a thing lies*

✅ **passed** in 10s over 4 step(s)

> **Asked** What items lie on the ground in the Clocktower, and whereabouts does a White cog spawn?

**What it did**

> *I'll look up the Clocktower location first.*

```text
get_thing(name='Clocktower', type='location')
get_thing(name='White cog', type='item')
found_here(name='Clocktower', type='item')
found_in(name='White cog')
```

**What it said**

````markdown
The Clocktower has 6 item spawns on the ground:

- **White cog** — x 2577, y 9655, plane 0 (the only spawn it has anywhere)
- **Blue cog** — x 2574, y 9633, plane 0
- **Red cog** — x 2583, y 9613, plane 0
- **Rat poison** — x 2564, y 9662, plane 0
- **Child's blanket** — x 2570, y 9604, plane 0
- **Purple dye** — x 2563, y 3261, plane 0

Note the first five sit in the underground dungeon coordinates (y ~9600s), while the purple dye is on the surface.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'cog' |

<sub>[back to the table](#at-a-glance)</sub>

---

## reverse_skilling

*gathered_from and made_from, the two skilling links read backwards*

✅ **passed** in 17s over 4 step(s)

> **Asked** Where do Raw salmon come from, and what are Shrimps made from and with which skill?

**What it did**

> *I'll look up both items.*

```text
gathered_from(name='Raw salmon')
made_from(name='Shrimps')
```

> **It asked you** (`ask_for_more`)
>
> For Raw salmon I've seen 10 of the 16 fishing spots listed, and all 10 so far are identical (Fishing spot NPCs, Fishing level 30, 70 xp, Fly fishing rod). Shall I pull the remaining 6 to check they match?
>
> - shown 10 of 16
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
gathered_from(name='Raw salmon', offset=10)
```

**What it said**

````markdown
**Raw salmon** comes from 16 sources: 15 Fishing spot NPCs, all requiring Fishing level 30 with a Fly fishing rod for 70 experience, plus a Fish stall (scenery), stolen at Thieving level 42 for 42 experience.

**Shrimps** are made from Raw shrimps via **Cooking**, level 1, for 30 experience. (Note there are two items named "Raw shrimps" in the data — the cooking entry links to item 317.)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'cooking' |

<sub>[back to the table](#at-a-glance)</sub>

---

## shop_from_npc

*runs_shop and sells, a shop reached from the person behind the counter*

✅ **passed** in 11s over 3 step(s)

> **Asked** Which shop does Ava run, and what does it stock?

**What it did**

> *I'll look up Ava and the shop she runs.*

```text
search(words='Ava', type='npc')
runs_shop(name='Ava')
sells(name="Ava's Odds and Ends")
```

**What it said**

````markdown
Ava runs **Ava's Odds and Ends**, which stocks 5 items:

- **Feather** — stock 1000, 6 gp
- **Iron arrow** — stock 40, 20 gp
- **Steel arrow** — stock 10, 46 gp
- **Iron arrowtips** — stock 30, 26 gp
- **Steel arrowtips** — stock 20, 36 gp
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'arrowtips' |

<sub>[back to the table](#at-a-glance)</sub>

---

## master_tasks

*assigns and counts_towards, the slayer links read the other way*

✅ **passed** in 38s over 10 step(s)

> **Asked** What can Vannaka send me after, and which Slayer tasks does killing a Steel dragon count towards?

**What it did**

> *I'll look up both of these.*

```text
assigns(name='Vannaka')
counts_towards(name='Steel dragon')
get_thing(name='Vannaka', type='npc')
get_thing(name='npc:1597', type='npc')
assigns(name='npc:1597')
```

> **It asked you** (`ask_for_more`)
>
> Killing a Steel dragon counts towards one Slayer task: Steel dragons. For Vannaka (the Grand Exchange Slayer master, NPC 1597 — a second entry, 1596, only runs the Slayer Equipment shop and has no tasks listed), the wiki lists 43 assignable tasks. The first 10 by weight are: Banshee (6), Crawling hand (6), Crocodiles (6), Earth warriors (6), Green dragons (6), Ankou (7), Blue dragons (7), Brine rats (7), Cave bug (7), Cave crawlers (7). Shall I pull the remaining 33?
>
> - shown 10 of 43
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
assigns(name='npc:1597', offset=10)
assigns(name='npc:1597', offset=20)
assigns(name='npc:1597', offset=30)
assigns(name='npc:1597', offset=40)
```

**What it said**

````markdown
**Steel dragon:** killing one counts towards exactly one Slayer task — **Steel dragons**. (Note: Vannaka does *not* assign it.)

**Vannaka's 43 tasks**, by assignment weight:

- **Weight 6:** Banshee, Crawling hand, Crocodiles, Earth warriors, Green dragons
- **Weight 7:** Ankou, Blue dragons, Brine rats, Cave bug, Cave crawlers, Cave slimes, Dagannoths, Desert lizards, Elves, Fire giants, Ghouls, Hellhounds, Hill giants, Ice giants, Ice warrior, Kalphites, Kurasks, Lesser demons, Mogres, Moss giants, Ogres, Rock slugs, Trolls, Vampires, Werewolves
- **Weight 8:** Aberrant spectres, Basilisks, Bloodvelds, Cockatrices, Dust devils, Harpie bug swarms, Infernal mages, Jellies, Jungle horrors, Otherwordly being, Pyrefiends, Shade, Turoths
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 9 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'Steel dragon' |

<sub>[back to the table](#at-a-glance)</sub>

---

## search_words

*full text search over names and descriptions, rather than a lookup*

✅ **passed** in 9s over 1 step(s)

> **Asked** Search this wiki for anything with 'dragonfire' in it and tell me how many there are.

**What it did**

> *I'll search the wiki for anything with 'dragonfire' in the name.*

```text
search(words='dragonfire')
```

**What it said**

````markdown
The wiki has **2** things with 'dragonfire' in the name, both items and both called **Dragonfire shield** (ids 11283 and 11284), each described as "A heavy shield with a snarling, draconic visage." That's the full list — nothing further to page through.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |

<sub>[back to the table](#at-a-glance)</sub>

---

## multi_hop

*three links in a row, which no single tool answers*

✅ **passed** in 35s over 25 step(s)

> **Asked** I want a Slayer task that will earn me dragon bones. Work out which creatures drop them, which of those are a Slayer task, and which master hands that task out.

**What it did**

> *I'll start by finding which NPCs drop dragon bones.*

```text
dropped_by(name='Dragon bones')
```

> **It asked you** (`ask_for_more`)
>
> Dragon bones are dropped by 33 different NPCs — I've seen the first 10 (King Black Dragon, red/black/blue/green/bronze/iron/steel dragons). Shall I pull the remaining 23 droppers before checking which are Slayer-assignable?
>
> - shown 10 of 33
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
dropped_by(name='Dragon bones', offset=10)
dropped_by(name='Dragon bones', offset=20)
dropped_by(name='Dragon bones', offset=30)
counts_towards(name='npc:53')
counts_towards(name='npc:54')
counts_towards(name='npc:55')
counts_towards(name='npc:941')
counts_towards(name='npc:1590')
counts_towards(name='npc:1591')
counts_towards(name='npc:1592')
counts_towards(name='npc:50')
counts_towards(name='npc:5362')
counts_towards(name='npc:5363')
counts_towards(name='npc:113')
counts_towards(name='npc:6054')
assigned_by(name='task:68')
assigned_by(name='task:10')
assigned_by(name='task:12')
assigned_by(name='task:41')
assigned_by(name='task:14')
assigned_by(name='task:50')
assigned_by(name='task:81')
assigned_by(name='task:58')
```

**What it said**

````markdown
**Dragon bones droppers (33 NPC entries, 12 distinct):** every dragon type drops them at 1/1 — King Black Dragon, red, black, blue, green, bronze, iron, steel, brutal green and mithril dragons — plus Dragon impling (1/20) and Jogre (1/128).

**Which are Slayer tasks, and who assigns them:**

| Task | Assigned by (weight) |
|---|---|
| Blue dragons | Vannaka (7), Chaeldar (8) |
| Green dragons *(incl. brutal green)* | Vannaka (6) |
| Bronze dragons | Chaeldar (11) |
| Iron dragons | Chaeldar (12), Duradel (5) |
| Steel dragons | Duradel (7) |
| Black dragons *(incl. KBD)* | Duradel (9) |
| Mithril dragons | Duradel (9) |
| Red dragons | *no master assigns it in this data* |

Dragon implings and Jogres count towards no Slayer task. Best odds: Chaeldar for iron dragons (weight 12) or bronze (11); Duradel for black/mithril (9 each).
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 24 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'dragon' |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_chain

*a quest, the music it unlocks, and where in the world that music plays*

✅ **passed** in 16s over 11 step(s)

> **Asked** If I finish The Fremennik Isles, which music does it unlock, and whereabouts in the world do those tracks play?

**What it did**

> *I'll look up the quest and its music.*

```text
get_thing(name='The Fremennik Isles', type='quest')
music_heard(name='The Fremennik Isles')
found_in(name='Island of the Trolls')
found_in(name='Jester Minute')
found_in(name='Major Miner')
found_in(name='Norse Code')
found_in(name='Ogre the Top')
found_in(name='Volcanic Vikings')
get_thing(name='Jester Minute', type='music')
get_thing(name='Major Miner', type='music')
get_thing(name='Ogre the Top', type='music')
```

**What it said**

````markdown
The Fremennik Isles unlocks six tracks, all listed as unlocked "during Fremennik Isles":

- **Island of the Trolls** — plays in the Fremennik Isles
- **Norse Code** — plays in Jatizso
- **Volcanic Vikings** — plays in Neitiznot
- **Major Miner** and **Ogre the Top** (Ogre set) — each recorded as playing in 1 map square, but the wiki doesn't name the location
- **Jester Minute** — recorded as playing in 0 map squares, i.e. cutscene/quest-only, with no world location
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 11 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'Volcanic Vikings' |
| ✅ | the answer carries 'Neitiznot' |

<sub>[back to the table](#at-a-glance)</sub>

---

## fuzzy_name

*a misspelt name settled by asking rather than by guessing*

✅ **passed** in 27s over 7 step(s)

> **Asked** tell me about the abysal wipe

**What it did**

```text
search(words='abysal wipe')
search(words='abyssal whip')
get_thing(name='item:4151', type='item')
get_thing(name='item:4178', type='item')
```

> **It asked you** (`ask_to_choose`)
>
> I read "abysal wipe" as the Abyssal whip — there are two items by that name in the wiki. Which one do you want?
>
> - Abyssal whip (item 4151) — the standard one: weapon slot, 70 Attack, special attack, value 120,001, market price 1,121,785
> - Abyssal whip (item 4178) — a duplicate/no-equip-slot version: value 6, market price 6
>
> **You answered** *the probe's own answer*
>
> item

> **It asked you** (`ask_to_choose`)
>
> Sorry — both are items, so that doesn't narrow it. Which of the two Abyssal whip entries should I describe?
>
> - The one with ID 4151 (equippable, 70 Attack, special attack, worth ~1.1M)
> - The one with ID 4178 (value 6 gp)
>
> **You answered** *the probe's own answer*
>
> Abyssal whip

> **It asked you** (`ask_to_confirm`)
>
> Shall I go with the main Abyssal whip (item ID 4151)?
>
> - proposing: You mean the standard, equippable Abyssal whip (ID 4151) — the one dropped by Abyssal demons and sold in Armour &amp; Supplies — rather than the 6 gp duplicate entry (ID 4178).
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

**What it said**

````markdown
The **Abyssal whip** (item 4151) is a slash weapon from the Abyss: weapon slot, 0.45 kg, 4-tick attack speed, with a special attack, requiring **70 Attack**.

Bonuses are +82 slash attack and +82 strength, with nothing in any other attack, defence or prayer slot. It's tradeable (buy limit 10), value 120,001 gp, high alch 72,001 and low alch 48,000; the market record shows a price of 1,121,785 gp (low 1,121,785, high 1,574,876, median 1,260,973 over 113 snapshots, confidence "traded").

It's dropped by Abyssal demons (2 entries) and sold in the Armour & Supplies shop.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | it turned back to ask: ask_to_choose, ask_to_confirm |
| ✅ | the answer carries 'Abyssal whip' |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_name

*one name held by two sorts of thing, settled by asking which was meant*

⚠️ **fell short** in 7s over 1 step(s)

> **Asked** tell me about Monkey Madness

**What it did**

> *I'll look that up.*

```text
get_thing(name='Monkey Madness', type='quest')
```

**What it said**

````markdown
The wiki's entry for **Monkey Madness** (quest #75) is quite thin — it records only that it is **members only**, and that one music track, **"Suspicious"**, is heard during it.

There are no requirements, rewards, items, NPCs or locations linked to it in this build, so I can't tell you anything further about it from the tools.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ❌ | it settled the question itself instead of asking |
| ⚠️ | the answer never mentions 'Ape Atoll' |

<sub>[back to the table](#at-a-glance)</sub>

---

## vague_question

*a question too vague to look anything up for, so it must be narrowed*

✅ **passed** in 45s over 10 step(s)

> **Asked** what is the best weapon?

**What it did**

> **It asked you** (`ask_to_clarify`)
>
> "Best weapon" depends on what you're measuring and what you can use — could you narrow it down? For example: which combat style (melee, ranged, magic), which stat you want maximised (e.g. highest strength bonus, highest slash attack, fastest attack speed), and any limits like free-to-play only, a combat/skill level cap, or a budget?
>
> **You answered** *the probe's own answer*
>
> best for melee, at attack level 70

```text
compare_by_number(type='item', holds='attack level requirement', how='equals', number=70)
compare_by_number(type='item', ordered_by='Strength bonus', holds='Strength bonus', how='at_least', number=70, descending=True, limit=25)
compare_by_number(type='item', ordered_by='Strength bonus', holds='Strength bonus', how='at_least', number=70, descending=True)
compare_by_number(type='item', ordered_by='Strength bonus', holds='Strength bonus', how='at_least', number=70, descending=True, offset=10)
get_thing(name='Abyssal whip', type='item')
get_thing(name="Dharok's greataxe", type='item')
get_thing(name='Barrelchest anchor', type='item')
compare_by_number(type='item', ordered_by='Strength bonus', holds='Strength bonus', how='at_least', number=78, descending=True, offset=20)
get_thing(name='Saradomin sword', type='item')
```

**What it said**

````markdown
At 70 Attack, the wiki's strongest melee options are:

- **Dharok's greataxe** — Strength 105, Slash 103, but 7-tick speed and two-handed (needs 70 Attack *and* 70 Strength).
- **Dragon 2h sword** (Str 93) and **Dragon halberd** (Str 89) sit below it, and everything with more Strength (godswords at 132, Vesta's/Statius' gear, Barrelchest anchor) is over the 70 Attack line or not requirement-listed.
- For actual damage output, **Abyssal whip** (Slash 82, Strength 82, 4 ticks, one-handed, special attack) is the classic 70 Attack pick; the **Saradomin sword** matches its 82/82 at 4 ticks with +2 Prayer, but is two-handed and pricier (market 3,040,793 vs the whip's 1,121,785).

The wiki records no damage-per-second figure, so this comparison is from the listed bonuses and attack speeds only.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 9 time(s) |
| ✅ | it turned back to ask: ask_to_clarify |

<sub>[back to the table](#at-a-glance)</sub>

---

## honest_gap

*a fact this build lacks, which should be said rather than invented*

✅ **passed** in 11s over 2 step(s)

> **Asked** What does completing Desert Treasure reward you with?

**What it did**

> *I'll look up that quest.*

```text
get_thing(name='Desert Treasure', type='quest')
requires(name='Desert Treasure')
```

**What it said**

````markdown
The wiki entry for Desert Treasure records only **3 quest points** as a reward — it holds no other reward details (no XP, items or unlocks are listed in this build).

What it does record is the entry requirements: Firemaking 50, Magic 50, Slayer 10, Thieving 53, plus completion of six quests (The Dig Site, The Tourist Trap, Temple of Ikov, Priest in Peril, Waterfall Quest and Troll Stronghold). It's a master-difficulty, long, members-only quest in the Mahjarrat series.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer says the wiki does not hold this |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_gap

*a track unlocked by content this build holds no entity for*

✅ **passed** in 9s over 2 step(s)

> **Asked** Which quest do I have to finish to unlock the track Melodrama?

**What it did**

> *I'll look up that music track.*

```text
get_thing(name='Melodrama', type='music')
heard_during(name='Melodrama')
```

**What it said**

````markdown
Melodrama isn't tied to a quest at all — the wiki lists no quests it's heard during. It's unlocked during the Castle Wars minigame, and Castle Wars is the only location it plays in (set: Yanille(?), 1 map square).
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Castle Wars' |
| ✅ | the answer says the wiki does not hold this |

<sub>[back to the table](#at-a-glance)</sub>

---

## filter_by_attribute

*picking things out by a number rather than by name*

✅ **passed** in 14s over 3 step(s)

> **Asked** Which weapons give more than 100 strength bonus? Name them and say how much each one gives.

**What it did**

> *I'll look for items with a strength bonus above 100.*

```text
compare_by_number(type='item', holds='strength bonus', how='more_than', number=100, descending=True)
```

> **It asked you** (`ask_for_more`)
>
> I've found 18 items with a strength bonus over 100, and I've read the top 10 so far (ranging from 132 down to 105). Shall I pull the remaining 8?
>
> - shown 10 of 18
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
compare_by_number(type='item', holds='strength bonus', how='more_than', number=100, descending=True, offset=10)
```

**What it said**

````markdown
18 items have a strength bonus above 100:

- **132** — Armadyl godsword, Bandos godsword, Saradomin godsword, Zamorak godsword
- **122** — Vesta's spear, Vesta's spear (deg)
- **118** — Vesta's longsword, Vesta's longsword (deg), Corrupt vesta's longsword, C. vesta's longsword (deg)
- **114** — Statius's warhammer, Statius' warhammer (deg), Corrupt statius's warhammer
- **105** — Dharok's greataxe, plus its charged variants (Dharok's axe 100, 75, 50 and 25)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'godsword' |

<sub>[back to the table](#at-a-glance)</sub>

---

## order_by_attribute

*asking for the cheapest or largest of something*

✅ **passed** in 14s over 3 step(s)

> **Asked** What is the cheapest food that restores more than 10 hitpoints, and how much does it restore?

**What it did**

```text
compare_by_number(type='item', holds='hitpoints restored', how='more_than', number=10)
compare_by_number(type='item', holds='Restores', how='more_than', number=10, ordered_by='Market price', limit=20)
compare_by_number(type='item', holds='Restores', how='more_than', number=10, ordered_by='Market price')
```

**What it said**

````markdown
Four items tie for cheapest, all at a market price of 2 gp:

- **Tangled toads' legs** — restores 15
- **Worm hole** — restores 12
- **Cheese+tom batta**, **Fruit batta**, **Vegetable batta** — restore 11 each

So the best of the cheapest is Tangled toads' legs at 2 gp for 15 hitpoints. (Next cheapest after those is Egg potato at 13 gp, restoring 11; 37 items in total restore more than 10.)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer says the wiki does not hold this |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_spread

*a number the newest sort of thing records, ordered largest first*

✅ **passed** in 11s over 4 step(s)

> **Asked** Which music plays across the most map squares in the world, and how many does it play in?

**What it did**

```text
compare_by_number(type='music', descending=True)
list_sorts()
compare_by_number(type='music', ordered_by='Map squares it plays in', descending=True, limit=5)
compare_by_number(type='music', ordered_by='Map squares it plays in', descending=True)
```

**What it said**

````markdown
Three tracks tie for the most, each playing in 9 map squares: **Bounty Hunter Level 1**, **Bounty Hunter Level 2**, and **Bounty Hunter Level 3**. Next behind them are Clan Wars (6) and Volcanic Vikings (5).
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Bounty Hunter' |

<sub>[back to the table](#at-a-glance)</sub>

---

## price_over_time

*how a price moved, rather than what it is now*

✅ **passed** in 12s over 2 step(s)

> **Asked** Has the Abyssal whip gone up or down over the last year, and by how much?

**What it did**

> *I'll check the price history for the Abyssal whip.*

```text
how_the_price_moved(name='Abyssal whip')
how_the_price_moved(name='Abyssal whip', since='2025-08-01')
```

**What it said**

````markdown
Down. Over the last year of readings (2025-08-02 to 2026-08-01, 53 readings, marked as genuinely traded), the Abyssal whip fell from 1,253,222 to 1,121,785 gp — a drop of 131,437 gp, or -10.5%. That 1,121,785 is also its low for the period.

For context, across the whole record (from 2024-06-08) it's down 453,091 gp, or -28.8%, from 1,574,876. Note the data ends 2026-08-01, so "the last year" here means the year up to that date.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer says the wiki does not hold this |

<sub>[back to the table](#at-a-glance)</sub>
