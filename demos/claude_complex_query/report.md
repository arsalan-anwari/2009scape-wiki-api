# Complex query sweep

*Questions of every shape this wiki can be asked, put to one model, with everything it read and everything it said.*

`2026-08-15 20:11`

|  |  |
| --- | --- |
| **model** | `claude-opus-5` |
| **dataset** | `data/knowledge.sqlite3` |
| **wiki** | 32 tools, started as `scape2009-wiki-mcp` |
| **probes** | 41 |
| **answers** | scripted |

## At a glance

**41 of 41** probes showed everything asked of them, in 10m 17s.

|  | probe | steps | took | what it covers |
| :-: | --- | --: | --: | --- |
| ✅ | [manifest](#manifest) | 2 | 8s | the written surface: what this build is and what sorts it holds |
| ✅ | [browse_rooms](#browse_rooms) | 6 | 26s | listing a whole sort, and construction room attributes |
| ✅ | [item_value](#item_value) | 2 | 11s | item attributes: market price, price confidence and equipment bonuses |
| ✅ | [npc_stats](#npc_stats) | 2 | 11s | npc combat attributes, under a name eighteen records used to answer to |
| ✅ | [scenery_use](#scenery_use) | 2 | 8s | scenery as an entity type, with the options the game gives it |
| ✅ | [quest_detail](#quest_detail) | 5 | 21s | quest attributes authored by hand, and what a quest asks you to bring |
| ✅ | [slayer_task](#slayer_task) | 3 | 11s | the task entity type and the advice it carries |
| ✅ | [shop_currency](#shop_currency) | 1 | 6s | a pointer attribute resolving to a named thing rather than an id |
| ✅ | [place_hierarchy](#place_hierarchy) | 1 | 7s | a place described by what it is and what it sits inside, not by tiles |
| ✅ | [place_contents](#place_contents) | 2 | 7s | the part_of / contains pair, a place read from both ends |
| ✅ | [music_track](#music_track) | 1 | 7s | music as an entity type, with the set and the sentence it carries |
| ✅ | [music_place](#music_place) | 4 | 13s | located_in with music at one end, from the track and from the place |
| ✅ | [quest_music](#quest_music) | 2 | 7s | heard_during and music_heard, the newest link read both ways |
| ✅ | [drops_paged](#drops_paged) | 7 | 23s | a drop table too long for one answer, so the reader is asked first |
| ✅ | [rare_drops](#rare_drops) | 7 | 19s | a roll on a table many monsters share, read as the items it gives |
| ✅ | [unplayable_quest](#unplayable_quest) | 1 | 7s | a quest the game declares but no class implements |
| ✅ | [who_drops_it](#who_drops_it) | 3 | 15s | following a link backwards, from an item to everything that drops it |
| ✅ | [what_wants_it](#what_wants_it) | 2 | 9s | the requires / needed_for pair, which the quest overlays feed |
| ✅ | [narrowed_walk](#narrowed_walk) | 1 | 8s | a link answering with several sorts, narrowed to one of them |
| ✅ | [shop_lines](#shop_lines) | 4 | 10s | shops from both ends, with price and who stands behind the counter |
| ✅ | [slayer_chain](#slayer_chain) | 2 | 8s | assigns / assigned_by and satisfied_by, the two slayer links |
| ✅ | [skilling](#skilling) | 11 | 46s | yields and makes: gathering a resource and turning it into something |
| ✅ | [ammunition](#ammunition) | 3 | 16s | the uses_ammunition pair, followed both ways between two items |
| ✅ | [spawns](#spawns) | 4 | 13s | located_in both ways: what lies in a place, and where a thing lies |
| ✅ | [smithing_bar](#smithing_bar) | 2 | 16s | makes, from one ingredient to everything the game turns it into |
| ✅ | [reverse_skilling](#reverse_skilling) | 2 | 7s | gathered_from and made_from, the two skilling links read backwards |
| ✅ | [shop_from_npc](#shop_from_npc) | 3 | 10s | runs_shop and sells, a shop reached from the person behind the counter |
| ✅ | [master_tasks](#master_tasks) | 7 | 25s | assigns and counts_towards, the slayer links read the other way |
| ✅ | [search_words](#search_words) | 1 | 7s | full text search over names and descriptions, rather than a lookup |
| ✅ | [multi_hop](#multi_hop) | 23 | 29s | three links in a row, which no single tool answers |
| ✅ | [music_chain](#music_chain) | 11 | 18s | a quest, the music it unlocks, and where in the world that music plays |
| ✅ | [fuzzy_name](#fuzzy_name) | 6 | 23s | a misspelt name settled by asking rather than by guessing |
| ✅ | [bad_spelling](#bad_spelling) | 5 | 18s | a name too badly spelt to search for, put back to whoever asked |
| ✅ | [music_name](#music_name) | 1 | 6s | one name held by two sorts of thing, told apart by what the asker said |
| ✅ | [vague_question](#vague_question) | 15 | 58s | a question too vague to look anything up for, so it must be narrowed |
| ✅ | [honest_gap](#honest_gap) | 1 | 9s | what a quest gives you, which only a community guide ever wrote down |
| ✅ | [music_gap](#music_gap) | 2 | 9s | a track unlocked by content this build holds no entity for |
| ✅ | [filter_by_attribute](#filter_by_attribute) | 3 | 17s | picking things out by a number rather than by name |
| ✅ | [order_by_attribute](#order_by_attribute) | 13 | 22s | ordering by a number, then pricing the answer over a shop counter |
| ✅ | [music_spread](#music_spread) | 5 | 15s | a number the newest sort of thing records, ordered largest first |
| ✅ | [price_over_time](#price_over_time) | 2 | 11s | how a price moved, rather than what it is now |

<sub>✅ showed everything asked of it, ⚠️ fell short of something, ❌ came apart, or said the wiki holds nothing where it does</sub>

### Tool coverage

**32 of 32** tools the wiki offers were called at least once.

### Turns back to you

| tool | times |
| --- | --: |
| `ask_for_more` | 7 |
| `ask_to_choose` | 4 |
| `ask_to_clarify` | 1 |
| `ask_to_confirm` | 1 |

---

## manifest

*the written surface: what this build is and what sorts it holds*

✅ **passed** in 8s over 2 step(s)

> **Asked** What is this wiki built from, and what sorts of thing does it know about? Give me the data version and the two largest sorts by count.

**What it did**

> *I'll check the build info and the type counts.*

```text
about()
list_sorts()
```

**What it said**

````markdown
This wiki is built from the **2009scape** game data, data version **2026.08.15.175358** (built 15 August 2026), and its two largest sorts are **items (6,033)** and **NPCs (3,105)**.

Everything it knows about, by count:

| Sort | Count |
| --- | --- |
| Items | 6,033 |
| NPCs | 3,105 |
| Scenery objects | 1,848 |
| Music tracks | 550 |
| Shops | 233 |
| Locations | 210 |
| Quests | 150 |
| Slayer tasks | 93 |
| House rooms | 27 |
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'item' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## browse_rooms

*listing a whole sort, and construction room attributes*

✅ **passed** in 26s over 6 step(s)

> **Asked** List the construction rooms this game has and tell me which is the most expensive to build, with its cost and the Construction level it needs.

**What it did**

> *I'll look up the construction rooms in the wiki.*

```text
list_things(type='room', limit=50)
compare_by_number(type='room', ordered_by='build cost', descending=True, limit=5)
compare_by_number(type='room', ordered_by='build cost', descending=True)
```

> ***Treasure room** is the most expensive: **250,000 coins**, requiring **Construction level 75**.*
>
> *The game has 27 buildable rooms in total. Here are the ten costliest:*
>
> *| Room | Build cost | Construction level |*
> *| --- | --- | --- |*
> *| Treasure room | 250,000 | 75 |*
> *| Oubilette | 150,000 | 65 |*
> *| Throne room | 150,000 | 60 |*
> *| Portal chamber | 100,000 | 50 |*
> *| Formal garden | 75,000 | 55 |*
> *| Chapel | 50,000 | 45 |*
> *| Costume room | 50,000 | 42 |*
> *| Study room | 50,000 | 40 |*
> *| Combat room | 25,000 | 32 |*
> *| Games room | 25,000 | 30 |*

> **It asked you** (`ask_for_more`)
>
> Shall I list the remaining rooms with their costs and level requirements?
>
> - shown 10 of 27
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
compare_by_number(type='room', ordered_by='build cost', descending=True, offset=10)
compare_by_number(type='room', ordered_by='build cost', descending=True, offset=20)
```

**What it said**

````markdown
Here are the remaining 17 rooms:

| Room | Build cost | Construction level |
| --- | --- | --- |
| Quest hall | 25,000 | 35 |
| Quest hall 2 | 25,000 | 35 |
| Skill hall | 15,000 | 25 |
| Bedroom | 10,000 | 20 |
| Dungeon pit | 10,000 | 70 |
| Workshop | 10,000 | 15 |
| Dungeon corridor | 7,500 | 70 |
| Dungeon junction | 7,500 | 70 |
| Dungeon stairs | 7,500 | 70 |
| Dining room | 5,000 | 10 |
| Kitchen | 5,000 | 5 |
| Garden | 1,000 | 1 |
| Parlour | 1,000 | 1 |
| Skill hall 2 | 0 | 25 |
| Roof 2 exit | 0 | — |
| Roof 3 exit | 0 | — |
| Roof 4 exit | 0 | — |

The wiki records no Construction level for the three roof exit rooms.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 5 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Treasure room' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## item_value

*item attributes: market price, price confidence and equipment bonuses*

✅ **passed** in 11s over 2 step(s)

> **Asked** How much is Statius's warhammer worth on the market, how much can I trust that price, and what does it do for my strength?

**What it did**

> *I'll look that up.*

```text
get_thing(name="Statius's warhammer")
how_the_price_moved(name="Statius's warhammer")
```

**What it said**

````markdown
**Statius's warhammer sits at 6,893,037 gp, on a "traded" price record you can rely on, and gives +114 Strength bonus.**

- **Market price** — 6,893,037 gp, from 113 readings, confidence rated "traded" (genuine trade activity, not a guess).
- **Price range on record** — low 6,200,000 gp, high 6,973,417 gp, median 6,583,712 gp.
- **Trend** — up 353,037 gp (+5.4%) from 6,540,000 gp on 2024-06-08 to 6,893,037 gp on 2026-08-01.
- **Strength bonus** — +114, alongside +123 Crush attack (but -4 Stab and -4 Slash).
- **Other stats** — 6 tick attack speed, has a special attack, requires level 78 Attack, and degrades in combat until it turns to dust.
- **Alchemy** — 180,000 gp high alch, 120,000 gp low alch, shop value 300,000 gp.

Note there are also separate entries for the degraded and corrupt versions of this hammer, which carry their own stats and prices — ask if you want those instead.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'traded' |
| ✅ | the answer carries '114' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## npc_stats

*npc combat attributes, under a name eighteen records used to answer to*

✅ **passed** in 11s over 2 step(s)

> **Asked** How dangerous is a Tormented demon? Give me its combat stats.

**What it did**

```text
search(words='Tormented demon', type='npc')
get_thing(name='Tormented demon', type='npc')
```

**What it said**

````markdown
**A Tormented demon is a serious threat: 326 lifepoints, all combat levels at 85, and huge defences (394 slash defence) behind a damage-halving protection prayer.**

- **Lifepoints** — 326
- **Combat levels** — Attack 85, Strength 85, Defence 85, Magic 85, Ranged 85
- **Attack speed** — 6 ticks
- **Attack bonuses** — Stab 112, Slash 132, Crush 113, Magic 111, Ranged 245
- **Defence bonuses** — Stab 167, Slash 394, Crush 346, Magic 213, Ranged 349, Summoning 167
- **Other bonuses** — Strength 65, Prayer 39, Magic damage 65, Ranged strength 58
- **Behaviour** — aggressive, attacks with magic, protects against melee, immune to poison, roams up to 40 tiles, respawns after 100 ticks
- **Rewards** — 136 Slayer experience per kill, and 85 possible drops

The wiki doesn't record a combat level or max hit for it.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries '326' |
| ✅ | the answer carries '85' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## scenery_use

*scenery as an entity type, with the options the game gives it*

✅ **passed** in 8s over 2 step(s)

> **Asked** What can I do with a Bank booth, and how many are in the world?

**What it did**

```text
get_thing(name='Bank booth')
compare_by_number(type='scenery', named='Bank booth')
```

**What it said**

````markdown
**96 bank booths stand in the world**, and you can Use, Use-quickly or Collect at them.

- **Use / Use-quickly** — the bank teller serves you from the booth, opening your bank.
- **Collect** — picks up items waiting for you (the collection service).
- **Members only** — no; it's a free-to-play object, taking up a single tile.
- **Where** — recorded in 24 locations, including Varrock, Al Kharid and Canifis.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Collect' |
| ✅ | the answer carries '96' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## quest_detail

*quest attributes authored by hand, and what a quest asks you to bring*

✅ **passed** in 21s over 5 step(s)

> **Asked** How hard is Desert Treasure, how long does it take, what series is it part of, which skills does it want, and what must I bring with me?

**What it did**

> *I'll look up the quest.*

```text
get_thing(name='Desert Treasure', type='quest')
requires(name='Desert Treasure')
```

> **It asked you** (`ask_for_more`)
>
> I've got the quest's difficulty, length, series and skills, plus the first 10 of its 22 listed requirements (items and prerequisite quests). Shall I pull the remaining 12 so I can give you the full bring-with-you list?
>
> - shown 10 of 22
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
requires(name='Desert Treasure', offset=10)
requires(name='Desert Treasure', offset=20)
```

**What it said**

````markdown
**Desert Treasure is a master-difficulty, long quest in the Mahjarrat series**, worth 3 quest points and members-only.

**Skills**
- **Required** — Firemaking 50, Magic 50, Slayer 10, Thieving 53
- **Recommended** — Prayer 43

**Items to bring** (16 listed)
- **Pestle and mortar**, **Bones**, **Ashes**, **Charcoal**, **Garlic** — ingredients
- **Blood rune**, **Molten glass**, **Silver bar**, **Spice**, **Note**
- **Tinderbox** and **Magic logs** — for the firemaking step
- **Ice gloves**, **Spiked boots**, **Face mask** — worn gear
- **Chocolate cake**

**Quests you must finish first** (6)
- **The Dig Site**, **The Tourist Trap**, **Temple of Ikov**, **Priest in Peril**, **Waterfall Quest**, **Troll Stronghold**

You start by talking to **Eblis** in the Kharidian Desert, and finishing it gives **20,000 Magic XP** plus access to the Ancient Magicks spellbook, the ancient staff from Eblis, a ring of visibility and the Zaros altar under the desert pyramid.

The wiki doesn't record an estimated completion time in minutes — only the "long" length rating.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'master' |
| ✅ | the answer carries 'Mahjarrat' |
| ✅ | the answer carries 'thieving' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## slayer_task

*the task entity type and the advice it carries*

✅ **passed** in 11s over 3 step(s)

> **Asked** What Slayer level do I need before I can be sent after Skeletal wyverns, and what does the game warn me about them?

**What it did**

```text
get_thing(name='Skeletal wyvern')
search(words='skeletal wyvern')
get_thing(name='task:75', type='task')
```

**What it said**

````markdown
**Slayer level 72** (plus combat level 70) before Skeletal wyverns can be assigned.

- **The warning** — they're extremely dangerous and hard to hit with arrows, as the arrows slip right through them; to stand a good chance of surviving you'll need elemental shielding from their icy breath.
- **Shields that count** — Elemental shield, Mind shield or Dragonfire shield.
- **Assigned by** — Duradel only.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries '72' |
| ✅ | the answer carries 'elemental' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## shop_currency

*a pointer attribute resolving to a named thing rather than an id*

✅ **passed** in 6s over 1 step(s)

> **Asked** What does Tzhaar-mej-roh's Rune Store take as payment?

**What it did**

```text
get_thing(name="Tzhaar-mej-roh's Rune Store", type='shop')
```

**What it said**

````markdown
**Tokkul.**

- **Tzhaar-mej-roh's Rune Store** — trades in Tokkul rather than coins, is not a general store, and does not buy alchemy products. It's run by TzHaar-Mej-Roh and stocks 8 items, including fire, water and earth runes.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Tokkul' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## place_hierarchy

*a place described by what it is and what it sits inside, not by tiles*

✅ **passed** in 7s over 1 step(s)

> **Asked** Tell me about Draynor Manor: what sort of place is it, and what larger place is it part of?

**What it did**

> *I'll look that up.*

```text
get_thing(name='Draynor Manor')
```

**What it said**

````markdown
**Draynor Manor is a building — the haunted manor north of Draynor Village — and it is part of Draynor Village.**

- **Kind** — building
- **Part of** — Draynor Village
- **Found here** — 109 things are recorded at the manor, including a dead tree, candles and a tree
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Draynor Village' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## place_contents

*the part_of / contains pair, a place read from both ends*

✅ **passed** in 7s over 2 step(s)

> **Asked** List every place recorded inside Varrock, the whole list rather than a few examples, and tell me which larger place White Knights' Castle belongs to.

**What it did**

```text
contains(name='Varrock')
part_of(name="White Knights' Castle")
```

**What it said**

````markdown
**Varrock records two places inside it — Varrock Palace and Varrock Square — and White Knights' Castle is part of Falador.**

- **Varrock Palace** — a building within Varrock
- **Varrock Square** — an area within Varrock
- **White Knights' Castle** — belongs to the city of Falador

That is the complete list of two; nothing was left out.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | it followed the link this probe is here for: contains |
| ✅ | it followed the link this probe is here for: part_of |
| ✅ | the answer carries 'Varrock Square' |
| ✅ | the answer carries 'Falador' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_track

*music as an entity type, with the set and the sentence it carries*

✅ **passed** in 7s over 1 step(s)

> **Asked** Tell me about the music track Adventure: which set is it part of, and how is it unlocked?

**What it did**

> *I'll look that up.*

```text
get_thing(name='Adventure', type='music')
```

**What it said**

````markdown
**Adventure** belongs to the **Varrock** music set, and it unlocks at **Varrock Palace**.

- **Set** — Varrock
- **Unlocked** — at Varrock Palace
- **Where it plays** — the Palace and Varrock Palace areas (one map square)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Varrock Palace' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_place

*located_in with music at one end, from the track and from the place*

✅ **passed** in 13s over 4 step(s)

> **Asked** Where is the track Fanfare heard, and what does Varrock Palace hold?

**What it did**

> *I'll look up both.*

```text
get_thing(name='Fanfare')
get_thing(name='Varrock Palace')
found_in(name='Fanfare')
found_here(name='Varrock Palace')
```

**What it said**

````markdown
**Fanfare plays in Falador**, and **Varrock Palace holds five quests and one music track**.

Fanfare (Falador music set, unlocked at Falador Castle) is heard in:
- **Falador** — the city
- **Park** — an area
- **White Knights' Castle** — a building

Varrock Palace, King Roald's palace in northern Varrock:
- **Adventure** — music track, part of the Varrock set, unlocked here
- **Shield of Arrav** — novice quest, medium, 1 quest point, free-to-play
- **Priest in Peril** — intermediate quest, medium, 1 quest point, members
- **All Fired Up** — intermediate quest, medium, 1 quest point, members
- **Garden of Tranquility** — intermediate quest, long, not playable on this server
- **Defender of Varrock** — master quest, long, members, not playable on this server
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'Falador' |
| ✅ | the answer carries 'Adventure' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## quest_music

*heard_during and music_heard, the newest link read both ways*

✅ **passed** in 7s over 2 step(s)

> **Asked** Which pieces of music play during Dream Mentor, and which quest is the track Suspicious heard during?

**What it did**

> *I'll look up both.*

```text
music_heard(name='Dream Mentor')
heard_during(name='Suspicious')
```

**What it said**

````markdown
**Six tracks play during Dream Mentor, and Suspicious is heard during Monkey Madness.**

- **Everlasting** — unlocked during Dream Mentor
- **Illusive** — unlocked during Dream Mentor
- **Inadequacy** — unlocked during Dream Mentor
- **Untouchable** — unlocked during Dream Mentor
- **Down and Out** — unlocked during Dream Mentor
- **On the Up** — unlocked during Dream Mentor

Note that the wiki marks Monkey Madness as not playable on this server.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Monkey Madness' |
| ✅ | the answer carries 'Everlasting' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## drops_paged

*a drop table too long for one answer, so the reader is asked first*

✅ **passed** in 23s over 7 step(s)

> **Asked** What does the King Black Dragon drop? There are a lot, so show me the first few and check with me before reading the rest.

**What it did**

> *I'll look up the King Black Dragon's drops.*

```text
drops(name='King Black Dragon')
```

> *The **King Black Dragon has 53 drops**; here are the first 10.*
>
> *| Drop | Chance | Market price |*
> *| --- | --- | --- |*
> *| Dragon bones | 1/1 | 2,627 |*
> *| Black dragonhide | 1/1 | 2,694 |*
> *| Crimson charm | 1/2 | — (untradeable) |*
> *| Coins | 1/20 | — |*
> *| Adamant platebody | 1/20 | 9,688 |*
> *| Rune longsword | 1/20 | 29,484 |*
> *| Mithril 2h sword | 1/20 | 3,302 |*
> *| Adamant 2h sword | 1/20 | 4,235 |*
> *| Adamant axe | 1/20 | 2,201 |*
> *| Mithril battleaxe | 1/20 | 1,955 |*

> **It asked you** (`ask_for_more`)
>
> That's the first 10 of the King Black Dragon's 53 drops. Shall I read on through the rest?
>
> - shown 10 of 53
>
> **You answered** *the probe's own answer*
>
> yes, show me the rest

```text
drops(name='King Black Dragon', offset=10)
drops(name='King Black Dragon', offset=20)
drops(name='King Black Dragon', offset=30)
drops(name='King Black Dragon', offset=40)
drops(name='King Black Dragon', offset=50)
```

**What it said**

````markdown
Here are the remaining 43 drops, from most to least common.

| Drop | Chance | Market price |
| --- | --- | --- |
| Amulet of strength | 1/20 | 2,216 |
| Air rune | 1/20 | 17 |
| Fire rune | 1/20 | 17 |
| Rune bolts | 1/20 | 440 |
| Gold charm | 1/22 | — (untradeable) |
| Green charm | 1/24 | — (untradeable) |
| Shark | 1/41 | 555 |
| Oyster | 1/41 | 220 |
| Iron ore | 1/41 | 209 |
| Blood rune | 1/41 | 261 |
| Iron arrow | 1/41 | 18 |
| Yew logs | 1/41 | 263 |
| Adamantite bar | 1/41 | 2,125 |
| Death rune | 1/41 | 310 |
| Law rune | 1/41 | 378 |
| Runite limbs | 1/41 | 14,813 |
| Blue charm | 1/72 | — (untradeable) |
| Kbd heads | 1/128 | — (untradeable) |
| Uncut sapphire | 1/2908 | 673 |
| Steel arrow | 1/3489 | 75 |
| Uncut emerald | 1/3489 | 1,153 |
| Uncut ruby | 1/4361 | 1,377 |
| Silver ore | 1/4984 | 205 |
| Tooth half of a key | 1/4984 | 29,676 |
| Loop half of a key | 1/4984 | 30,699 |
| Rune sq shield | 1/4984 | 27,875 |
| Rune 2h sword | 1/4984 | 38,771 |
| Rune battleaxe | 1/4984 | 31,832 |
| Chaos talisman | 1/4984 | 1,663 |
| Nature talisman | 1/4984 | 4,155 |
| Uncut diamond | 1/4984 | 5,496 |
| Runite bar | 1/4984 | 11,387 |
| Draconic visage | 1/5000 | 62,500,000 |
| Nature rune | 1/5815 | 307 |
| Adamant javelin | 1/5815 | 102 |
| Rune arrow | 1/5815 | 205 |
| Dragonstone | 1/6978 | 60,822 |
| Rune javelin | 1/8723 | 109 |
| Rune kiteshield | 1/8723 | 48,214 |
| Dragon med helm | 1/11630 | 88,118 |
| Rune spear | 1/34891 | 28,502 |
| Dragon spear | 1/34891 | 75,190 |
| Shield left half | 1/34891 | 210,997 |

Dragon bones and black dragonhide are the only guaranteed drops (1/1 each), and the Draconic visage at 1/5000 is by far the most valuable.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 6 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | it turned back to ask: ask_for_more |
| ✅ | the answer carries 'Dragon bones' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## rare_drops

*a roll on a table many monsters share, read as the items it gives*

✅ **passed** in 19s over 7 step(s)

> **Asked** Does the King Black Dragon drop a Draconic visage, and roughly how often? Name two of the rarest things it can drop besides that.

**What it did**

> *I'll look up the King Black Dragon's drop table.*

```text
get_thing(name='King Black Dragon', type='npc')
drops(name='King Black Dragon')
drops(name='King Black Dragon', offset=10)
drops(name='King Black Dragon', offset=20)
drops(name='King Black Dragon', offset=30)
drops(name='King Black Dragon', offset=40)
drops(name='King Black Dragon', offset=50)
```

**What it said**

````markdown
**Yes — the King Black Dragon drops a Draconic visage at 1/5000.**

Two of its rarest other drops, both from the rare drop table at **1/34,891**:

- **Shield left half** — the rarest tier of its table, worth about 210,997 coins
- **Dragon spear** — same 1/34,891 chance, worth about 75,190 coins

(A Rune spear shares that same 1/34,891 slot, and the next rarest after those is the Dragon med helm at 1/11,630.)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 7 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Draconic visage' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## unplayable_quest

*a quest the game declares but no class implements*

✅ **passed** in 7s over 1 step(s)

> **Asked** Is the quest Monkey Madness available in the game?

**What it did**

> *I'll look that up.*

```text
get_thing(name='Monkey Madness', type='quest')
```

**What it said**

````markdown
**No — Monkey Madness is in the wiki but is not playable on this server.**

- **Difficulty** — master, and a very long quest
- **Members only** — yes
- **Series** — Gnome
- **Start point** — King Narnode Shareen, at the Grand Tree

The entry exists (with its music track, *Suspicious*), but it is flagged as not playable in this game.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer says the wiki does not hold this |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## who_drops_it

*following a link backwards, from an item to everything that drops it*

✅ **passed** in 15s over 3 step(s)

> **Asked** Which monsters drop Dragon bones?

**What it did**

> *I'll look up what drops Dragon bones.*

```text
dropped_by(name='Dragon bones')
```

> **It asked you** (`ask_for_more`)
>
> I've got the first 10 of 13 monsters that drop Dragon bones — shall I pull the remaining 3?
>
> - shown 10 of 13
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
dropped_by(name='Dragon bones', offset=10)
```

**What it said**

````markdown
**13 monsters drop Dragon bones**, ten of them as a guaranteed drop.

| Monster | Drop chance | Combat level | Lifepoints |
|---|---|---|---|
| King Black Dragon | 1/1 | 276 | 240 |
| Black dragon | 1/1 | 227 | 190 |
| Red dragon | 1/1 | 152 | 140 |
| Blue dragon | 1/1 | 111 | 105 |
| Green dragon | 1/1 | 108 | 75 |
| Brutal green dragon | 1/1 | not recorded | 175 |
| Mithril dragon | 1/1 | not recorded | 254 |
| Bronze dragon | 1/1 | not recorded | 122 |
| Iron dragon | 1/1 | not recorded | 165 |
| Steel dragon | 1/1 | not recorded | 210 |
| Chaos Elemental | 1/10 | not recorded | 250 |
| Dragon impling | 1/20 | not recorded | 10 |
| Jogre | 1/128 | 57 | 70 |

The wiki lists no combat level for Brutal green, Mithril, Bronze, Iron and Steel dragons, the Chaos Elemental or the Dragon impling.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'dragon' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## what_wants_it

*the requires / needed_for pair, which the quest overlays feed*

✅ **passed** in 9s over 2 step(s)

> **Asked** Which quest wants me to bring an Iron chainbody, and what else does that quest ask for?

**What it did**

> *I'll look that up.*

```text
needed_for(name='Iron chainbody', type='quest')
requires(name="Black Knights' Fortress")
```

**What it said**

````markdown
**Black Knights' Fortress** is the quest that asks for an Iron chainbody.

Alongside it, the quest requires:

- **Bronze med helm** — worn on the head, market price 37
- **Cabbage** — market price 61
- **Iron chainbody** — worn on the chest, market price 254

It's a novice, short quest worth 3 quest points, free-to-play, and playable on this server.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Black Knights' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## narrowed_walk

*a link answering with several sorts, narrowed to one of them*

✅ **passed** in 8s over 1 step(s)

> **Asked** Animal Magnetism needs other quests finished and items carried. Ignore the quests: which items does it ask me to bring, and how many are there?

**What it did**

> *I'll look up the quest's requirements.*

```text
requires(name='Animal Magnetism', type='item')
```

**What it said**

````markdown
**Seven items to bring, plus one recommended.**

| Item | Kind | Market price |
|---|---|---|
| Ghostspeak amulet | Carried | Not tradeable |
| Mithril axe | Carried | 988 |
| Holy symbol | Carried | 2,429 |
| Hard leather | Carried | 634 |
| Hammer | Carried | 45 |
| Iron bar | Carried | 465 |
| Polished buttons | Carried | — |
| Amulet of glory | Recommended | 65,683 |

The wiki doesn't record a market price for polished buttons.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries '3' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## shop_lines

*shops from both ends, with price and who stands behind the counter*

✅ **passed** in 10s over 4 step(s)

> **Asked** Where can I buy Iron arrowtips and for how much, and who runs the shop you find them in?

**What it did**

> *I'll look this up.*

```text
sold_in(name='Iron arrowtips')
staffed_by(name="Dargaud's Bows And Arrows")
staffed_by(name="Ava's Odds and Ends")
staffed_by(name='Void Knight Archery Store')
```

**What it said**

````markdown
**Iron arrowtips cost 26 coins in all three shops that stock them.**

| Shop | Price | Stock | Run by |
|---|---|---|---|
| Dargaud's Bows And Arrows | 26 coins | 300 | Bow and Arrow salesman |
| Ava's Odds and Ends | 26 coins | 30 | Ava (with a Witch also staffing it) |
| Void Knight Archery Store | 26 coins | 100 | Squire |
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Ava' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## slayer_chain

*assigns / assigned_by and satisfied_by, the two slayer links*

✅ **passed** in 8s over 2 step(s)

> **Asked** Which Slayer masters can assign Aberrant spectres, and what creatures count towards a Steel dragons task?

**What it did**

```text
assigned_by(name='Aberrant spectres')
satisfied_by(name='Steel dragons')
```

**What it said**

````markdown
**Three masters assign Aberrant spectres — Duradel, Vannaka and Chaeldar — while a Steel dragons task is satisfied only by Steel dragons.**

- **Duradel** — assigns Aberrant spectres, task weight 7
- **Vannaka** — assigns Aberrant spectres, task weight 8
- **Chaeldar** — assigns Aberrant spectres, task weight 8
- **Steel dragon** — the sole creature counting towards a Steel dragons task; aggressive, 210 lifepoints
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Vannaka' |
| ✅ | the answer carries 'Steel dragon' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## skilling

*yields and makes: gathering a resource and turning it into something*

✅ **passed** in 46s over 11 step(s)

> **Asked** How many fishing spots are there in the game, what can I catch at one and at what levels, and what do raw shrimps turn into when cooked?

**What it did**

> *I'll look up fishing spots and raw shrimps.*

```text
search(words='fishing spot')
get_thing(name='Raw shrimps', type='item')
compare_by_number(type='npc', named='Fishing spot')
compare_by_number(type='scenery', named='Fishing spot')
yields(name='scenery:8986')
yields(name='npc:6267')
get_thing(name='npc:6267')
makes(name='Raw shrimps')
```

> **It asked you** (`ask_for_more`)
>
> I've listed the 10 lowest-level catches at a fishing spot — want the remaining 14 (higher-level fish like salmon, lobster, shark, etc.)?
>
> - shown 10 of 24
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
yields(name='npc:6267', offset=10)
yields(name='npc:6267', offset=20)
```

**What it said**

````markdown
**Fishing spots appear in 157 locations across the game**, and a single spot can yield **24 different catches** from level 1 to level 76; raw shrimps cook into **Shrimps**.

| Catch | Fishing level | XP | Tool |
|---|---|---|---|
| Raw shrimps | 1 | 10 | Small fishing net |
| Raw crayfish | 1 | 10 | Crayfish cage |
| Raw sardine | 5 | 20 | Fishing rod |
| Raw karambwanji | 5 | 5 | Small fishing net |
| Raw herring | 10 | 30 | Fishing rod |
| Raw anchovies | 15 | 40 | Small fishing net |
| Raw mackerel | 16 | 20 | Big fishing net |
| Seaweed | 16 | 1 | Big fishing net |
| Raw trout | 20 | 50 | Fly fishing rod |
| Raw cod | 23 | 45 | Big fishing net |
| Raw pike | 25 | 60 | Fishing rod |
| Slimy eel | 28 | 65 | Fishing rod |
| Raw salmon | 30 | 70 | Fly fishing rod |
| Frog spawn | 33 | 75 | Small fishing net |
| Raw tuna | 35 | 80 | Harpoon |
| Raw cave eel | 38 | 80 | Fishing rod |
| Raw rainbow fish | 38 | 80 | Fly fishing rod |
| Raw lobster | 40 | 90 | Lobster pot |
| Raw bass | 46 | 100 | Big fishing net |
| Raw swordfish | 50 | 100 | Harpoon |
| Raw lava eel | 53 | 60 | Oily fishing rod |
| Raw monkfish | 62 | 120 | Small fishing net |
| Raw karambwan | 65 | 105 | Karambwan vessel |
| Raw shark | 76 | 110 | Harpoon |

On the cooking: **Shrimps** — cooked at Cooking level 1 for 30 Cooking XP.

Two notes on the count: the fishable spot is a single entry that spawns at 157 recorded locations, and there is separately a "Fishing spot" scenery object (the Net one, 22 standing in the world) which the wiki records no catches for.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 10 time(s) |
| ✅ | it read the wiki 5 different ways |
| ✅ | the answer carries 'Shrimps' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## ammunition

*the uses_ammunition pair, followed both ways between two items*

✅ **passed** in 16s over 3 step(s)

> **Asked** What ammunition does a Phoenix crossbow take, and which other weapons fire Bronze bolts?

**What it did**

> *I'll look up both parts of this.*

```text
uses_ammunition(name='Phoenix crossbow')
used_by(name='Bronze bolts')
used_by(name='Bronze bolts', offset=10)
```

**What it said**

````markdown
**The Phoenix crossbow takes seven kinds of bolt, and ten other weapons fire Bronze bolts.**

Ammunition the Phoenix crossbow accepts:

- **Bronze bolts** — plain, market price 11 gp
- **Bronze bolts(p)** — poisoned, 3 gp
- **Bronze bolts(p+)** — 3 gp
- **Bronze bolts(p++)** — 3 gp
- **Opal bolts** — 6 gp
- **Opal bolts (e)** — enchanted, 6 gp
- **Broad-tipped bolts** — 92 gp

Other weapons that fire Bronze bolts:

| Weapon | Market price | Weight |
|---|---|---|
| Crossbow | 369 gp | 8 kg |
| Bronze crossbow | 126 gp | 4 kg |
| Blurite crossbow | not traded | 4 kg |
| Iron crossbow | 209 gp | 4 kg |
| Steel crossbow | 518 gp | 5 kg |
| Black crossbow | 800 gp | 5 kg |
| Mith crossbow | 1,756 gp | 6 kg |
| Dorgeshuun c'bow | 2,630 gp | 2.2 kg |
| Adamant crossbow | 4,451 gp | 6 kg |
| Rune crossbow | 20,029 gp | 6 kg |
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'bolts' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## spawns

*located_in both ways: what lies in a place, and where a thing lies*

✅ **passed** in 13s over 4 step(s)

> **Asked** What items lie on the ground in the Clocktower, and whereabouts does a White cog spawn?

**What it did**

```text
search(words='Clocktower')
get_thing(name='White cog', type='item')
found_here(name='Clocktower', type='item')
get_thing(name='Clocktower', type='location')
```

**What it said**

````markdown
**Six items spawn on the ground in the Clocktower**, including the White cog — though the wiki records only that it spawns in the Clocktower, with no more precise spot than that.

- **White cog** — 1 kg, "a cog from some machinery"
- **Blue cog** — 1 kg
- **Red cog** — 1 kg
- **Rat poison** — 0.1 kg
- **Child's blanket** — 0.9 kg
- **Purple dye** — 1 kg equivalent not recorded; tradeable, market price 150

The wiki holds no room-by-room or floor detail for where within the Clocktower any of these lie, so the White cog's exact spawn point isn't something it records.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'cog' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## smithing_bar

*makes, from one ingredient to everything the game turns it into*

✅ **passed** in 16s over 2 step(s)

> **Asked** I have a Bronze bar. What can I smith from it, and what Smithing level does each one need? Give me the cheapest handful.

**What it did**

> *I'll look up what a Bronze bar makes.*

```text
makes(name='Bronze bar')
```

> **It asked you** (`ask_to_choose`)
>
> The Bronze bar makes 26 different things. By "cheapest handful", which do you mean?
>
> - The lowest Smithing level ones (easiest to make)
> - The lowest market price ones (worth the least)
>
> **You answered** *the standing answer, unasked*
>
> the first one, The lowest Smithing level ones (easiest to make)

**What it said**

````markdown
**Bronze dagger and Bronze axe, both at level 1**, are the lowest-requirement things a Bronze bar makes.

| Item | Smithing level | Experience | Market price |
|---|---|---|---|
| Bronze dagger | 1 | 12.5 | 94 gp |
| Bronze axe | 1 | 12.5 | 49 gp |
| Bronze mace | 2 | 12.5 | not recorded |
| Bronze med helm | 3 | 12.5 | 37 gp |
| Bronze bolts (unf) | 3 | 12.5 | 2 gp |
| Bronze dart tip | 4 | 12.5 | 26 gp |
| Bronze sword | 4 | 12.5 | 26 gp |
| Bronze wire | 4 | 12.5 | 285 gp |
| Bronze nails | 4 | 12.5 | 16 gp |
| Bronze arrowtips | 5 | 12.5 | 16 gp |

That's the 10 lowest-level of 26 items in total. The wiki holds no market price for the Bronze mace. Say the word if you want the remaining 16.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | it followed the link this probe is here for: makes |
| ✅ | the answer carries 'Bronze dagger' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## reverse_skilling

*gathered_from and made_from, the two skilling links read backwards*

✅ **passed** in 7s over 2 step(s)

> **Asked** Where do Raw salmon come from, and what are Shrimps made from and with which skill?

**What it did**

```text
gathered_from(name='Raw salmon')
made_from(name='Shrimps')
```

**What it said**

````markdown
**Raw salmon come from fly fishing spots and the fish stall; Shrimps are cooked from Raw shrimps using Cooking.**

- **Fishing spot** — Fishing level 30, 70 Fishing XP, needs a Fly fishing rod
- **Fish stall** — Thieving level 42, 42 Thieving XP (steal-from)
- **Shrimps** — made from Raw shrimps, Cooking level 1, 30 Cooking XP
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'cooking' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## shop_from_npc

*runs_shop and sells, a shop reached from the person behind the counter*

✅ **passed** in 10s over 3 step(s)

> **Asked** Which shop does Ava run, and what does it stock?

**What it did**

> *I'll look up Ava first.*

```text
search(words='Ava', type='npc')
runs_shop(name='Ava')
sells(name="Ava's Odds and Ends")
```

**What it said**

````markdown
Ava runs **Ava's Odds and Ends**, a coin-based specialist shop stocking five items.

| Item | Stock | Shop price | Market price |
| --- | --- | --- | --- |
| Feather | 1000 | 6 | 19 |
| Iron arrow | 40 | 20 | 18 |
| Steel arrow | 10 | 46 | 75 |
| Iron arrowtips | 30 | 26 | 20 |
| Steel arrowtips | 20 | 36 | 68 |
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'arrowtips' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## master_tasks

*assigns and counts_towards, the slayer links read the other way*

✅ **passed** in 25s over 7 step(s)

> **Asked** What can Vannaka send me after, and which Slayer tasks does killing a Steel dragon count towards?

**What it did**

> *I'll look up both.*

```text
assigns(name='Vannaka')
counts_towards(name='Steel dragon')
```

> **It asked you** (`ask_for_more`)
>
> Vannaka assigns 43 different Slayer tasks — I've read the first 10 so far. Shall I pull the remaining 33 and list them all?
>
> - shown 10 of 43
>
> **You answered** *the standing answer, unasked*
>
> yes, go on

```text
assigns(name='Vannaka', offset=10)
assigns(name='Vannaka', offset=20)
assigns(name='Vannaka', offset=30)
assigns(name='Vannaka', offset=40)
```

**What it said**

````markdown
**Vannaka assigns 43 different tasks, and killing a Steel dragon counts only towards the Steel dragons task.**

Steel dragons — needs Slayer level 1 but combat level 85, and Vannaka is not one of the masters who gives it.

Vannaka's 43 tasks, grouped by how often they come up (weight 8 is most likely, 6 least):

- **Weight 8** — Aberrant spectres (Slayer 60, combat 65), Basilisks (40/40), Bloodvelds (50/50), Cockatrices (25/25), Dust devils (65/70), Harpie bug swarms (33/45), Infernal mages (45/40), Jellies (52/57), Jungle horrors (1/65), Otherwordly being (1/40), Pyrefiends (30/25), Shade (1/30), Turoths (55/60)
- **Weight 7** — Ankou (1/40), Blue dragons (1/65), Brine rats (47/45), Cave bug (7/1), Cave crawlers (10/10), Cave slimes (17/15), Dagannoths (1/75), Desert lizards (22/15), Elves (1/70), Fire giants (1/65), Ghouls (1/25), Hellhounds (1/75), Hill giants (1/25), Ice giants (1/50), Ice warrior (1/45), Kalphites (1/15), Kurasks (70/65), Lesser demons (1/60), Mogres (32/1), Moss giants (1/40), Ogres (1/40), Rock slugs (20/20), Trolls (1/60), Vampires (1/35), Werewolves (1/60)
- **Weight 6** — Banshee (15/20), Crawling hand (5/1), Crocodiles (1/50), Earth warriors (1/35), Green dragons (1/52)
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 6 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Steel dragon' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## search_words

*full text search over names and descriptions, rather than a lookup*

✅ **passed** in 7s over 1 step(s)

> **Asked** Search this wiki for anything with 'dragonfire' in it and tell me how many there are.

**What it did**

> *I'll search the wiki for anything with "dragonfire" in the name.*

```text
search(words='dragonfire')
```

**What it said**

````markdown
**One.**

- **Dragonfire shield** (item) — a heavy shield with a snarling, draconic visage.

That is the only thing in the wiki whose name contains "dragonfire". Note that this search matches names only, so items like anti-dragon shields or dragonfire-related potions that don't carry the word in their name wouldn't show up here.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## multi_hop

*three links in a row, which no single tool answers*

✅ **passed** in 29s over 23 step(s)

> **Asked** I want a Slayer task that will earn me dragon bones. Work out which creatures drop them, which of those are a Slayer task, and which master hands that task out.

**What it did**

> *I'll start by finding which creatures drop dragon bones.*

```text
dropped_by(name='Dragon bones')
dropped_by(name='Dragon bones', offset=10)
```

> *Now let me check which of these count towards Slayer tasks.*

```text
counts_towards(name='Blue dragon')
counts_towards(name='Red dragon')
counts_towards(name='Black dragon')
counts_towards(name='Green dragon')
counts_towards(name='Bronze dragon')
counts_towards(name='Iron dragon')
counts_towards(name='Steel dragon')
counts_towards(name='Mithril dragon')
counts_towards(name='Brutal green dragon')
counts_towards(name='King Black Dragon')
counts_towards(name='Jogre')
counts_towards(name='Chaos Elemental')
counts_towards(name='Dragon impling')
```

> *Now let me find which masters assign each of these tasks.*

```text
assigned_by(name='Blue dragons')
assigned_by(name='Red dragons')
assigned_by(name='Black dragons')
assigned_by(name='Green dragons')
assigned_by(name='Bronze dragons')
assigned_by(name='Iron dragons')
assigned_by(name='Steel dragons')
assigned_by(name='Mithril dragons')
```

**What it said**

````markdown
**Seven dragon tasks drop dragon bones at a guaranteed 1/1 rate, and Duradel hands out the most of them (four).**

| Task | Master(s) | Dragon-bone droppers it covers | Combat level needed |
|---|---|---|---|
| Green dragons | Vannaka | Green dragon, Brutal green dragon | 52 |
| Blue dragons | Vannaka, Chaeldar | Blue dragon | 65 |
| Bronze dragons | Chaeldar | Bronze dragon | 75 |
| Iron dragons | Chaeldar, Duradel | Iron dragon | 80 |
| Black dragons | Duradel | Black dragon, King Black Dragon | 80 |
| Steel dragons | Duradel | Steel dragon | 85 |
| Mithril dragons | Duradel | Mithril dragon | 60 |

Every one of these drops dragon bones on every kill, and all seven tasks need only **Slayer level 1** — combat level is the only gate.

Worth knowing:
- **Red dragon** drops dragon bones and the "Red dragons" task exists, but no master in the wiki assigns it, so you can't get it as a task.
- **Jogre** (1/128), **Chaos Elemental** (1/10) and **Dragon impling** (1/20) also drop dragon bones but count towards no Slayer task at all.
- If you want the assignment most often, Duradel's dragon tasks carry weights of 9 (black), 9 (mithril), 7 (steel) and 5 (iron); Chaeldar's iron dragons is weight 12 and bronze dragons weight 11.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 23 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'dragon' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_chain

*a quest, the music it unlocks, and where in the world that music plays*

✅ **passed** in 18s over 11 step(s)

> **Asked** If I finish The Fremennik Isles, which music does it unlock, and whereabouts in the world do those tracks play?

**What it did**

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
**Six tracks unlock during The Fremennik Isles**, but the wiki only names a play location for three of them.

| Track | Where it plays | Set |
|---|---|---|
| Norse Code | Jatizso | Fremennik Isles |
| Volcanic Vikings | Neitiznot | Fremennik Isles |
| Island of the Trolls | Fremennik Isles (the Trollweiss/troll island area) | Ogre |
| Ogre the Top | not named — it covers one map area, but the wiki doesn't say which | Ogre |
| Major Miner | not named — it covers one map area, but the wiki doesn't say which | — |
| Jester Minute | nowhere on the map; it's a cutscene/quest-only piece | — |

One caveat: the wiki lists The Fremennik Isles as **not playable on this server**, so the quest can't currently be completed to unlock them.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 11 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | the answer carries 'Volcanic Vikings' |
| ✅ | the answer carries 'Neitiznot' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## fuzzy_name

*a misspelt name settled by asking rather than by guessing*

✅ **passed** in 23s over 6 step(s)

> **Asked** tell me about the abysal wipe

**What it did**

```text
get_thing(name='abysal wipe')
search(words='abysal wipe')
```

> **It asked you** (`ask_to_choose`)
>
> Nothing on the wiki answers to "abysal wipe". What sort of thing did you mean, so I can look up the closest real names?
>
> - An item
> - An NPC
> - A piece of scenery
> - Something else (tell me what)
>
> **You answered** *the probe's own answer*
>
> an item, yes

```text
find_close_names(name='abysal wipe', type='item', limit=6, keep=0.5)
```

> **It asked you** (`ask_to_choose`)
>
> Which of these items did you mean?
>
> - Abyssal whip
> - Abyssal head
> - Abyssal demon
> - Abyssal book
> - Abyssal titan pouch
> - Abyssal charm
>
> **You answered** *the probe's own answer*
>
> Abyssal whip

```text
get_thing(name='Abyssal whip', type='item')
```

**What it said**

````markdown
**Abyssal whip** — a slash weapon from the Abyss, needing **level 70 Attack** to wield.

- **Combat bonuses** — Slash attack +82, Strength +82, nothing else
- **Speed** — 4 ticks, and it has a special attack
- **Weight** — 0.45 kg, weapon slot, tradeable and lendable
- **Value** — 120,001 gp; high alchemy 72,001 gp, low alchemy 48,000 gp
- **Market price** — 1,121,785 gp (median 1,260,973, ranging 1,121,785–1,574,876 across 113 snapshots)
- **Buy limit** — 10
- **Where it comes from** — dropped by the Abyssal demon, and sold in the Armour & Supplies shop
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 4 time(s) |
| ✅ | it read the wiki 3 different ways |
| ✅ | it turned back to ask: ask_to_choose |
| ✅ | the answer carries 'Abyssal whip' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## bad_spelling

*a name too badly spelt to search for, put back to whoever asked*

✅ **passed** in 18s over 5 step(s)

> **Asked** whats the drangon scimatar worth

**What it did**

```text
get_thing(name='drangon scimatar')
```

> **It asked you** (`ask_to_confirm`)
>
> Nothing in the wiki answers to "drangon scimatar" — before I look for close names, can you confirm what sort of thing you mean?
>
> - proposing: You're after an item (a weapon), and you want its value/price.
>
> **You answered** *the probe's own answer*
>
> an item, yes

```text
find_close_names(name='drangon scimatar', type='item', limit=5)
```

> **It asked you** (`ask_to_choose`)
>
> The closest real item name in the wiki is this one — is it the one you mean?
>
> - Dragon scimitar
>
> **You answered** *the probe's own answer*
>
> Dragon scimitar

```text
get_thing(name='Dragon scimitar', type='item')
```

**What it said**

````markdown
**The Dragon scimitar's market price is 108,704 gp.**

- **Market range** — low 105,060, high 108,959, median 105,841 (from 113 snapshots, confidence: traded)
- **Shop value** — 100,000 gp
- **High alchemy** — 60,000 gp; **Low alchemy** — 40,000 gp
- **Buy limit** — 10, and it's tradeable
- **Sold in** — Armour & Supplies, and Daga's Scimitar Smithy
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 3 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | it turned back to ask: ask_to_choose, ask_to_confirm |
| ✅ | it followed the link this probe is here for: find_close_names |
| ✅ | the answer carries 'Dragon scimitar' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_name

*one name held by two sorts of thing, told apart by what the asker said*

✅ **passed** in 6s over 1 step(s)

> **Asked** Where is the music track Monkey Madness unlocked in the game?

**What it did**

> *I'll look that up.*

```text
get_thing(name='Monkey Madness', type='music')
```

**What it said**

````markdown
**On Ape Atoll.**

- **Where it plays** — Ape Atoll and Marim, covering two map squares
- **Music set** — Jungle
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Ape Atoll' |
| ✅ | the answer carries 'Jungle' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## vague_question

*a question too vague to look anything up for, so it must be narrowed*

✅ **passed** in 58s over 15 step(s)

> **Asked** what is the best weapon?

**What it did**

> **It asked you** (`ask_to_clarify`)
>
> "Best" depends on what you're measuring — could you narrow it down? Specifically: (1) which combat style you mean (melee, ranged or magic), and (2) what counts as best for you — highest attack bonus, highest strength/damage bonus, highest price, or something else like a level requirement you need to stay under?
>
> **You answered** *the probe's own answer*
>
> best for melee, at attack level 70

```text
compare_by_number(type='item', holds='attack level requirement', how='at_most', number=70, ordered_by='strength bonus', descending=True)
compare_by_number(type='item', holds='Level', how='at_most', number=70, ordered_by='Strength bonus', descending=True, limit=15)
compare_by_number(type='item', holds='Level', how='at_most', number=70, ordered_by='Strength bonus', descending=True)
compare_by_number(type='item', ordered_by='Strength bonus', descending=True)
get_thing(name='Abyssal whip', type='item')
get_thing(name='Zamorakian spear', type='item')
compare_by_number(type='item', ordered_by='Strength bonus', descending=True, offset=10)
compare_by_number(type='item', ordered_by='Strength bonus', descending=True, offset=20)
get_thing(name="Dharok's greataxe", type='item')
get_thing(name="Statius's warhammer", type='item')
get_thing(name='Barrelchest anchor', type='item')
get_thing(name='Dragon 2h sword', type='item')
get_thing(name='Saradomin sword', type='item')
get_thing(name='Dragon halberd', type='item')
```

**What it said**

````markdown
**Dharok's greataxe** — at Attack 70 nothing you can wield has a bigger strength bonus (105), though it swings slowly at 7 ticks; if you want steady damage rather than big hits, the **Abyssal whip** (82 strength, 4 ticks) is the fastest thing in that bracket.

| Weapon | Strength bonus | Best attack bonus | Attack speed | Requirements |
|---|---|---|---|---|
| Dharok's greataxe | 105 | 103 slash | 7 ticks | Attack 70, Strength 70 |
| Barrelchest anchor | 100 | 92 crush | 6 ticks | none recorded |
| Dragon 2h sword | 93 | 92 slash | 7 ticks | Attack 60 |
| Dragon halberd | 89 | 95 slash | 7 ticks | Attack 60, Strength 30 |
| Abyssal whip | 82 | 82 slash | 4 ticks | Attack 70 |
| Saradomin sword | 82 | 82 slash | 4 ticks | Attack 70 |
| Zamorakian spear | 75 | 85 stab | 4 ticks | Attack 70 |

The tier above these is out of reach for you: the godswords need Attack 75, Vesta's longsword and Statius's warhammer need Attack 78.

The wiki records equipment bonuses and speeds, not damage-per-second, so "best" here is by bonus and speed rather than a calculated DPS figure.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 14 time(s) |
| ✅ | it turned back to ask: ask_to_clarify |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## honest_gap

*what a quest gives you, which only a community guide ever wrote down*

✅ **passed** in 9s over 1 step(s)

> **Asked** What does completing Desert Treasure reward you with?

**What it did**

> *I'll look that up.*

```text
get_thing(name='Desert Treasure', type='quest')
```

**What it said**

````markdown
**Completing Desert Treasure gives 3 quest points, 20,000 Magic XP, and unlocks the Ancient Magicks spellbook.**

- **Experience** — 20,000 Magic XP
- **Quest points** — 3
- **Ancient Magicks** — the spellbook is unlocked, and you switch between it and your normal book at the pyramid altar
- **Ancient staff** — you can buy one from Eblis afterwards
- **Ring of visibility** — kept as a reward
- **Zaros altar** — the altar beneath the desert pyramid becomes available

For reference, it's a master-difficulty, long, members-only quest in the Mahjarrat series, started by talking to Eblis in the Kharidian Desert. It needs Firemaking 50, Magic 50, Slayer 10 and Thieving 53, with Prayer 43 recommended.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 1 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'Ancient Magicks' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_gap

*a track unlocked by content this build holds no entity for*

✅ **passed** in 9s over 2 step(s)

> **Asked** Which quest do I have to finish to unlock the track Melodrama?

**What it did**

> *I'll look up the music track Melodrama.*

```text
get_thing(name='Melodrama', type='music')
heard_during(name='Melodrama')
```

**What it said**

````markdown
**None — Melodrama isn't tied to a quest at all.**

- **How it unlocks** — during the Castle Wars minigame.
- **Where it plays** — Castle Wars.

The wiki lists no quest connected to this track, so there's nothing to finish for it.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Castle Wars' |
| ✅ | the answer says the wiki does not hold this |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## filter_by_attribute

*picking things out by a number rather than by name*

✅ **passed** in 17s over 3 step(s)

> **Asked** Which weapons give more than 100 strength bonus? Name them and say how much each one gives.

**What it did**

> *I'll look up items by strength bonus.*

```text
compare_by_number(type='item', holds='strength bonus', how='more_than', number=100, descending=True)
```

> **It asked you** (`ask_for_more`)
>
> I've got the top 10 weapons by strength bonus (Armadyl/Bandos godswords at 132 down to the Dharok's axes at 105) — there are 18 items above 100 in total. Shall I pull the remaining 8?
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
**18 weapons beat 100 strength bonus, topped by the four godswords at +132.**

| Weapon | Strength bonus |
|---|---|
| Armadyl, Bandos, Saradomin & Zamorak godswords | 132 |
| Vesta's spear (also the degraded version) | 122 |
| Vesta's longsword (also degraded, corrupt and corrupt degraded) | 118 |
| Statius's warhammer (also degraded and corrupt) | 114 |
| Dharok's greataxe (also the 100, 75, 50 and 25 charge versions) | 105 |

That's every item above +100 in the weapon slot — the degraded and charge-count variants carry the same bonus as the full versions.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer carries 'godsword' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## order_by_attribute

*ordering by a number, then pricing the answer over a shop counter*

✅ **passed** in 22s over 13 step(s)

> **Asked** Which foods restore more than 15 hitpoints? Of those, which is the cheapest to buy over a shop counter, which shop sells it, and what does that shop charge for it?

**What it did**

```text
compare_by_number(type='item', holds='hitpoints restored', how='more_than', number=15, descending=True)
compare_by_number(type='item', holds='Restores', how='more_than', number=15, descending=True, limit=50)
compare_by_number(type='item', holds='Restores', how='more_than', number=15, descending=True)
sold_in(name='Cooked karambwan')
sold_in(name='Curry')
sold_in(name='Manta ray')
sold_in(name='Monkfish')
sold_in(name='Mushroom potato')
sold_in(name='Potato with cheese')
sold_in(name='Sea turtle')
sold_in(name='Shark')
sold_in(name='Stuffed snake')
sold_in(name='Tuna potato')
```

**What it said**

````markdown
**Tuna potato is the cheapest over a counter — 113 coins at Delicious Goods**, and it also heals the most of any food (22).

Ten foods restore more than 15 hitpoints:

| Food | Restores | Cheapest shop price | Shop |
|---|---|---|---|
| Tuna potato | 22 | 113 coins | Delicious Goods |
| Manta ray | 22 | 500 coins | Delicious Goods |
| Sea turtle | 21 | — | not sold in any shop |
| Shark | 20 | 300 coins | Keepa Kettilon's store, Delicious Goods |
| Mushroom potato | 20 | — | not sold in any shop |
| Stuffed snake | 20 | — | not sold in any shop |
| Curry | 19 | — | not sold in any shop |
| Cooked karambwan | 18 | 460 coins | The Shrimp and Parrot, Delicious Goods |
| Monkfish | 16 | 230 coins | Arnold's Eclectic Supplies, Delicious Goods |
| Potato with cheese | 16 | 350 coins | Warriors' Guild Food Shop |

The wiki also lists Potato with cheese at The Fairy's Culinary Goods but records no price for it there, so that stock can't be compared.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 13 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | it followed the link this probe is here for: sold_in |
| ✅ | the answer carries 'Tuna potato' |
| ✅ | the answer carries 'Delicious Goods' |
| ✅ | the answer carries '113' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## music_spread

*a number the newest sort of thing records, ordered largest first*

✅ **passed** in 15s over 5 step(s)

> **Asked** Which music plays across the most map squares in the world, and how many does it play in?

**What it did**

```text
compare_by_number(type='music', holds='map squares', descending=True)
list_sorts()
compare_by_number(type='music', holds='Map squares it plays in', descending=True, number=1)
compare_by_number(type='music', ordered_by='Map squares it plays in', descending=True, limit=5)
compare_by_number(type='music', ordered_by='Map squares it plays in', descending=True)
```

**What it said**

````markdown
**Bounty Hunter Level 1, 2 and 3 — nine map squares each.** Three separate tracks tie for the widest coverage in the wiki.

- **Bounty Hunter Level 1** — 9 map squares, unlocked while playing Bounty Hunter
- **Bounty Hunter Level 2** — 9 map squares, unlocked while playing Bounty Hunter
- **Bounty Hunter Level 3** — 9 map squares, unlocked while playing Bounty Hunter

Next widest is **Clan Wars** at 6, then **Volcanic Vikings** at 5.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 5 time(s) |
| ✅ | it read the wiki 2 different ways |
| ✅ | the answer carries 'Bounty Hunter' |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>

---

## price_over_time

*how a price moved, rather than what it is now*

✅ **passed** in 11s over 2 step(s)

> **Asked** Has the Abyssal whip gone up or down over the last year, and by how much?

**What it did**

> *I'll check the price history for the Abyssal whip.*

```text
how_the_price_moved(name='Abyssal whip')
how_the_price_moved(name='Abyssal whip', since='2025-08-01')
```

**What it said**

````markdown
**Down 131,437 coins over the last year — a fall of 10.5%.**

- **Opened** — 1,253,222 coins on 2 August 2025
- **Closed** — 1,121,785 coins on 1 August 2026
- **Range over the year** — high of 1,253,222, low of 1,121,785 (it ended at its lowest point)
- **Readings** — 53 traded price points, so the trend is well supported

For context, over the full record the wiki holds (from June 2024), the whip is down 453,091 coins, or 28.8%.
````

**What happened**

|  |  |
| :-: | --- |
| ✅ | it read the wiki 2 time(s) |
| ✅ | it read the wiki 1 different ways |
| ✅ | the answer says the wiki does not hold this |
| ✅ | the answer names things rather than numbering them |

<sub>[back to the table](#at-a-glance)</sub>
