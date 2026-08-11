"""Read what a quest class asks of a player before it will let them start."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

SKILL: Final = r"Skills\.([A-Z_]+)"
QUEST: Final = r"Quests\.([A-Z][A-Z0-9_]*)"

#: Every spelling of a skill gate the game's code uses, with what to add to the
#: number so it reads as the level a player needs.
LEVELS: Final = (
    (re.compile(rf"hasLevelStat\s*\(\s*\w+\s*,\s*{SKILL}\s*,\s*(\d+)"), 0),
    (re.compile(rf"hasLevel\s*\(\s*{SKILL}\s*,\s*(\d+)"), 0),
    (
        re.compile(
            rf"(?:getStaticLevel|getLevel)\s*\(\s*{SKILL}\s*\)(?:!!)?\s*>=\s*(\d+)"
        ),
        0,
    ),
    (
        re.compile(
            rf"(?:getStaticLevel|getLevel)\s*\(\s*{SKILL}\s*\)(?:!!)?\s*>\s*(\d+)"
        ),
        1,
    ),
    (
        re.compile(
            rf"(?:getStaticLevel|getLevel)\s*\(\s*{SKILL}\s*\)(?:!!)?\s*<\s*(\d+)"
        ),
        0,
    ),
    (re.compile(rf"staticLevels\s*\[\s*{SKILL}\s*\](?:!!)?\s*>=\s*(\d+)"), 0),
    (re.compile(rf"staticLevels\s*\[\s*{SKILL}\s*\](?:!!)?\s*>\s*(\d+)"), 1),
)
FINISHED: Final = re.compile(
    rf"(?:isQuestComplete\s*\(\s*\w+\s*,\s*|isComplete\s*\(\s*){QUEST}"
)
POINTS: Final = re.compile(
    r"(?:getQuestPoints\s*\(\s*\w+\s*\)|questRepository\.points)\s*>=\s*(\d+)"
)
DECLARED: Final = re.compile(r"\b(?:fun|boolean)\s+hasRequirements\s*\(")
#: A quest naming a level outright rather than checking one, which settles it.
STATED: Final = re.compile(rf"SkillRequirement\s*\(\s*{SKILL}\s*,\s*(\d+)")
LITERAL: Final = re.compile(r'"([^"\n]*)"')
MARKUP: Final = re.compile(r"[^A-Za-z0-9]")
WORD: Final = re.compile(r"[a-z0-9]+")
#: What a journal line says when it is naming an advantage rather than a gate.
ADVICE: Final = re.compile(r"\b(advantage|advisable|recommend|suggest|useful|helpful)")
#: Words a quest constant carries that its journal line will not bother repeating.
SKIPPED_WORDS: Final = frozenset({"the", "a", "of"})
#: How far from a condition to look for the words shown beside it, when the line
#: holding it shows none of its own.
NEARBY: Final = 5


class QuestGates(BaseModel):
    """The levels, finished quests and quest points a quest asks for up front."""

    model_config = ConfigDict(frozen=True)

    skills: dict[str, int] = Field(default_factory=dict)
    quests: tuple[str, ...] = ()
    quest_points: int | None = None
    enforced: bool = False
    disputed: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.skills or self.quests or self.quest_points is not None)


def read_gates(source: str) -> QuestGates:
    """Read the start gates one quest class states, from the class alone."""
    stated = {skill: int(level) for skill, level in STATED.findall(source)}
    enforced = _enforced(source)
    read = enforced or source
    lines = read.splitlines()
    disputed: list[str] = []
    skills: dict[str, int] = dict(stated)
    for skill, level, at in _levels(read):
        if skill in stated:
            if stated[skill] != level:
                disputed.append(f"{skill.lower()} {stated[skill]}, not {level}")
            continue
        if enforced:
            skills[skill] = max(skills.get(skill, 0), level)
            continue
        words = _shown(lines, read.count("\n", 0, at))
        if ADVICE.search(words):
            continue
        if _states(skill, level, words):
            skills[skill] = max(skills.get(skill, 0), level)
        elif skill.lower() in words:
            disputed.append(f"{skill.lower()} {level} against the words beside it")
    quests: list[str] = []
    for match in FINISHED.finditer(read):
        constant = match.group(1)
        if not enforced:
            words = _shown(lines, read.count("\n", 0, match.start()))
            if ADVICE.search(words) or not _titled(constant, words):
                continue
        if constant not in quests:
            quests.append(constant)
    points = POINTS.findall(read) if enforced else []
    return QuestGates(
        skills=dict(sorted(skills.items())),
        quests=tuple(quests),
        quest_points=int(points[0]) if points else None,
        enforced=bool(enforced),
        disputed=tuple(sorted(set(disputed))),
    )


def _enforced(source: str) -> str:
    """The body of the class's own hasRequirements, or nothing when it declares none."""
    declared = DECLARED.search(source)
    if declared is None:
        return ""
    start = source.find("{", declared.end())
    if start < 0:
        return ""
    depth = 0
    for at in range(start, len(source)):
        if source[at] == "{":
            depth += 1
        elif source[at] == "}":
            depth -= 1
            if not depth:
                return source[start : at + 1]
    return ""


def _levels(read: str) -> Iterator[tuple[str, int, int]]:
    for pattern, adjust in LEVELS:
        for match in pattern.finditer(read):
            yield match.group(1), int(match.group(2)) + adjust, match.start()


def _shown(lines: Sequence[str], number: int) -> str:
    """The words a player is shown beside a condition, and only those."""
    here = LITERAL.findall(lines[number]) if number < len(lines) else []
    if not here:
        here = [
            one
            for near in lines[max(0, number - NEARBY) : number + NEARBY + 1]
            for one in LITERAL.findall(near)
        ]
    return " ".join(_words(" ".join(here)))


def _words(text: str) -> list[str]:
    return WORD.findall(MARKUP.sub(" ", text.replace("'", "")).lower())


def _states(skill: str, level: int, words: str) -> bool:
    """Whether the words shown name that skill at that level."""
    plain = skill.lower()
    shown = words.split()
    return str(level) in shown and any(
        word.startswith(plain) or plain.startswith(word)
        for word in shown
        if len(word) > 3
    )


def _titled(constant: str, words: str) -> bool:
    """Whether the words shown name the quest that constant stands for."""
    wanted = [one for one in constant.lower().split("_") if one not in SKIPPED_WORDS]
    shown = words.split()
    return bool(wanted) and all(_among(one, shown) for one in wanted)


def _among(wanted: str, shown: Sequence[str]) -> bool:
    """Whether a word appears, allowing for the plural a journal line may add."""
    if wanted in shown:
        return True
    return len(wanted) > 2 and any(
        one.startswith(wanted) or wanted.startswith(one)
        for one in shown
        if len(one) > 2
    )


# test cases

ENFORCED: Final = """
class TheGolemQuest : Quest(Quests.THE_GOLEM, 111, 110, 1) {
    override fun hasRequirements(player: Player): Boolean {
        return player.skills.getStaticLevel(Skills.CRAFTING) >= 20 &&
            player.skills.getStaticLevel(Skills.THIEVING) >= 25
    }
    override fun drawJournal(player: Player, stage: Int) {
        line(player, "Level 40 Mining would be an advantage", 12)
    }
}
"""

JOURNAL: Final = """
class TheDigSite : Quest(Quests.THE_DIG_SITE, 34, 33, 2) {
    override fun drawJournal(player: Player, stage: Int) {
        line(player, "Level 10 Agility", ln++,
            hasLevelStat(player, Skills.AGILITY, 10))
        line(player, "!!Level 25 Thieving??", ln++,
            hasLevelStat(player, Skills.THIEVING, 25))
    }
    fun mine(player: Player) {
        if (hasLevelStat(player, Skills.MINING, 60)) dig(player)
    }
}
"""


def test_a_class_that_turns_a_player_away_is_read_where_it_does_so() -> None:
    gates = read_gates(ENFORCED)
    assert gates.skills == {"CRAFTING": 20, "THIEVING": 25}
    assert gates.enforced is True


def test_what_its_journal_calls_an_advantage_is_not_a_requirement() -> None:
    assert "MINING" not in read_gates(ENFORCED).skills


def test_a_class_that_turns_nobody_away_is_read_from_the_words_it_shows() -> None:
    gates = read_gates(JOURNAL)
    assert gates.skills == {"AGILITY": 10, "THIEVING": 25}
    assert gates.enforced is False


def test_a_check_the_player_is_never_shown_is_not_a_requirement() -> None:
    assert "MINING" not in read_gates(JOURNAL).skills


def test_a_level_stated_one_above_the_check_reads_as_the_level_asked_for() -> None:
    source = """
    boolean hasRequirements(Player player) {
        return player.getSkills().getStaticLevel(Skills.FLETCHING) > 9;
    }
    """
    assert read_gates(source).skills == {"FLETCHING": 10}


def test_a_class_refusing_below_a_level_asks_for_that_level() -> None:
    source = """
    override fun hasRequirements(player: Player?): Boolean {
        if (player!!.skills.getLevel(Skills.CRAFTING) < 40) return false
        return true
    }
    """
    assert read_gates(source).skills == {"CRAFTING": 40}


def test_a_finished_quest_is_read_where_the_class_enforces_it() -> None:
    source = """
    fun hasRequirements(player: Player): Boolean {
        return isQuestComplete(player, Quests.PRIEST_IN_PERIL)
    }
    """
    assert read_gates(source).quests == ("PRIEST_IN_PERIL",)


def test_a_finished_quest_the_journal_names_in_words_is_read_too() -> None:
    source = """
    override fun drawJournal(player: Player, stage: Int) {
        line(player, "!!Completion of Priest in Peril??", line++,
            player.questRepository.isComplete(Quests.PRIEST_IN_PERIL))
    }
    """
    assert read_gates(source).quests == ("PRIEST_IN_PERIL",)


def test_a_finished_quest_the_journal_does_not_name_is_left_alone() -> None:
    source = """
    override fun drawJournal(player: Player, stage: Int) {
        line(player, "I should speak to the duke.", line++,
            player.questRepository.isComplete(Quests.RUNE_MYSTERIES))
    }
    """
    assert read_gates(source).quests == ()


def test_the_words_may_punctuate_a_quest_name_the_constant_does_not() -> None:
    source = """
    override fun drawJournal(player: Player, stage: Int) {
        if (isQuestComplete(player, Quests.BLACK_KNIGHTS_FORTRESS)) {
            line(player, "and after the !!Black Knights' Fortress??", 12)
        }
    }
    """
    assert read_gates(source).quests == ("BLACK_KNIGHTS_FORTRESS",)


def test_quest_points_are_read_only_where_a_class_enforces_them() -> None:
    source = """
    fun hasRequirements(player: Player): Boolean {
        return getQuestPoints(player) >= 55
    }
    """
    assert read_gates(source).quest_points == 55


def test_words_and_condition_that_disagree_are_refused_and_written_down() -> None:
    source = """
    override fun drawJournal(player: Player, stage: Int) {
        val shown = arrayOf("Level 36 Woodcutting")
        val met = booleanArrayOf(player.getSkills().hasLevel(Skills.WOODCUTTING, 35))
    }
    """
    gates = read_gates(source)
    assert gates.skills == {}
    assert gates.disputed == ("woodcutting 35 against the words beside it",)


def test_a_level_a_class_names_outright_settles_what_its_check_disagrees_with() -> None:
    source = """
    override fun drawJournal(player: Player, stage: Int) {
        val shown = arrayOf("Level 36 Woodcutting")
        val met = booleanArrayOf(player.getSkills().hasLevel(Skills.WOODCUTTING, 35))
    }
    override fun newInstance(o: Any?): Quest {
        requirements.add(SkillRequirement(Skills.WOODCUTTING, 36))
        return this
    }
    """
    gates = read_gates(source)
    assert gates.skills == {"WOODCUTTING": 36}
    assert gates.disputed == ("woodcutting 36, not 35",)


def test_a_class_stating_nothing_reads_as_nothing() -> None:
    assert not read_gates("class Cook : Quest(Quests.COOKS_ASSISTANT, 29, 28, 1)")
