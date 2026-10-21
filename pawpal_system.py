"""PawPal+ core classes, implemented from diagrams/uml.mmd.

Owner and Pet hold the data, Task is a passive record of what needs doing, and
Scheduler makes all the placement decisions. Scheduler takes a flat list of
tasks rather than an Owner, so how tasks are gathered can change without
touching the scheduling logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import count

# Priority labels, ranked most to least important. Used to validate Task.priority
# and to sort tasks in Scheduler.sort_tasks().
PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}

# How far ahead each frequency puts its next occurrence. "once" maps to None:
# it has no next occurrence, which is what makes it a one-off.
FREQUENCY_STEPS: dict[str, timedelta | None] = {
    "once": None,
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}

# Hands out a number to each task as it's created, so "the order they were
# added" survives being flattened out of per-pet lists. Only the order of
# these numbers matters, never the values themselves.
_added_order = count()


def _parse_hhmm(value: str) -> int:
    """Convert an "HH:MM" string into minutes since midnight."""
    try:
        hours, minutes = value.split(":")
        total = int(hours) * 60 + int(minutes)
    except ValueError:
        raise ValueError(f'time must look like "HH:MM", got {value!r}') from None
    if not 0 <= total < 24 * 60:
        raise ValueError(f"time must be within a single day, got {value!r}")
    return total


def _format_hhmm(total_minutes: int) -> str:
    """Convert minutes since midnight back into an "HH:MM" string."""
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _check_task_fields(
    title: str, duration_minutes: int, priority: str, frequency: str = "once"
) -> None:
    """Raise ValueError if these aren't usable task details.

    Shared by Task.__post_init__ and Task.update_details so a task can never be
    edited into a state it couldn't have been created in. Checks the candidate
    values before anything is assigned, so a rejected edit leaves the task
    exactly as it was.
    """
    if not title.strip():
        raise ValueError("task title cannot be empty")
    if priority not in PRIORITY_ORDER:
        raise ValueError(f"priority must be one of {sorted(PRIORITY_ORDER)}, got {priority!r}")
    if duration_minutes <= 0:
        raise ValueError(f"duration_minutes must be positive, got {duration_minutes}")
    if frequency not in FREQUENCY_STEPS:
        raise ValueError(
            f"frequency must be one of {sorted(FREQUENCY_STEPS)}, got {frequency!r}"
        )


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low" | "medium" | "high"
    preferred_block: str | None = None  # TimeBlock.label; a preference, not a hard constraint
    completed: bool = False
    pet: Pet | None = None  # back-reference, set by Pet.add_task()
    added_order: int = field(default_factory=lambda: next(_added_order))
    frequency: str = "once"  # "once" | "daily" | "weekly"
    due_date: date = field(default_factory=date.today)
    # The occurrence this one spawned when it was completed, so undoing the
    # completion can take it back again. Set by Pet.complete_task().
    spawned: Task | None = None

    def __post_init__(self) -> None:
        """Reject a blank title, unknown priority, duration, or frequency."""
        _check_task_fields(
            self.title, self.duration_minutes, self.priority, self.frequency
        )
        self.title = self.title.strip()

    def mark_complete(self) -> None:
        """Mark this task done. Safe to call on an already-completed task."""
        self.completed = True

    def update_details(
        self,
        title: str,
        duration_minutes: int,
        priority: str,
        preferred_block: str | None = None,
        frequency: str = "once",
        due_date: date | None = None,
    ) -> None:
        """Change this task's details, applying the same checks as construction.

        Leaves completion status and the pet back-reference alone: editing what
        a task is doesn't change who it belongs to or whether it's done. A
        due_date of None keeps the date the task already has.
        """
        _check_task_fields(title, duration_minutes, priority, frequency)
        self.title = title.strip()
        self.duration_minutes = duration_minutes
        self.priority = priority
        self.preferred_block = preferred_block
        self.frequency = frequency
        if due_date is not None:
            self.due_date = due_date

    def next_occurrence(self) -> Task | None:
        """A fresh, incomplete copy of this task, due on its next date.

        A task is one occurrence on one day - "feed Mochi on Tuesday" - and
        frequency is the instruction for building its successor: tomorrow for
        a daily task, next week for a weekly one, and nothing at all for a
        one-off. The copy isn't attached to a pet here; Pet.complete_task()
        decides which list it belongs in.

        The copy keeps the title, duration, priority, preferred block and
        frequency, starts out incomplete, and is dated one step on from this
        task's due date (see FREQUENCY_STEPS). Returns None for a "once" task.
        """
        step = FREQUENCY_STEPS[self.frequency]
        if step is None:
            return None
        return Task(
            title=self.title,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            preferred_block=self.preferred_block,
            frequency=self.frequency,
            due_date=self.due_date + step,
        )


@dataclass
class Pet:
    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject a blank name, the same rule update_details applies."""
        if not self.name.strip():
            raise ValueError("pet name cannot be empty")
        self.name = self.name.strip()
        self.species = self.species.strip()

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet and set the task's back-reference."""
        task.pet = self
        self.tasks.append(task)

    def complete_task(self, task: Task) -> Task | None:
        """Mark a task done and queue its next occurrence, if it has one.

        Task decides what comes next; this decides where it goes. Completing
        an already-completed task doesn't queue a second copy: the occurrence
        is remembered on task.spawned, so a second call returns the same one
        instead of making another.

        Returns the occurrence that was queued, or None for a one-off.
        """
        task.mark_complete()
        if task.spawned is None:
            follow_up = task.next_occurrence()
            if follow_up is not None:
                self.add_task(follow_up)
                task.spawned = follow_up
        return task.spawned

    def uncomplete_task(self, task: Task) -> Task | None:
        """Undo a completion, taking back the occurrence it queued.

        The queued occurrence is only withdrawn while it's still exactly what
        completing this task produced. Once it's been edited or completed in
        its own right it belongs to the user, so it stays and is simply cut
        loose from the task that spawned it.

        Returns the occurrence that was withdrawn, or None.
        """
        task.completed = False
        follow_up, task.spawned = task.spawned, None
        if follow_up is None or follow_up not in self.tasks:
            return None

        untouched = task.next_occurrence()
        if untouched is None or follow_up.completed:
            return None
        same = (
            follow_up.title,
            follow_up.duration_minutes,
            follow_up.priority,
            follow_up.preferred_block,
            follow_up.frequency,
            follow_up.due_date,
        ) == (
            untouched.title,
            untouched.duration_minutes,
            untouched.priority,
            untouched.preferred_block,
            untouched.frequency,
            untouched.due_date,
        )
        if not same:
            return None

        self.remove_task(follow_up)
        return follow_up

    def remove_task(self, task: Task) -> None:
        """Drop a task from this pet's list.

        Matches on identity rather than equality, so two identical-looking
        tasks ("Walk, 20 min, high") are still told apart.
        """
        self.tasks = [kept for kept in self.tasks if kept is not task]

    def update_details(self, name: str, species: str) -> None:
        """Rename this pet or change its species, rejecting a blank name.

        Species is free text (a breed, "dog", "leopard gecko"), so it is
        trimmed but not validated.
        """
        if not name.strip():
            raise ValueError("pet name cannot be empty")
        self.name = name.strip()
        self.species = species.strip()


@dataclass
class Owner:
    name: str
    pets: list[Pet] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject a blank name, the same rule rename() applies."""
        self.rename(self.name)

    def rename(self, name: str) -> None:
        """Rename the owner, rejecting a blank name."""
        if not name.strip():
            raise ValueError("owner name cannot be empty")
        self.name = name.strip()

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's household, if the name is free."""
        self._check_name_free(pet.name, pet)
        self.pets.append(pet)

    def update_pet(self, pet: Pet, name: str, species: str) -> None:
        """Edit one of this owner's pets, keeping names unique.

        Uniqueness is a property of the household rather than of any one pet,
        so it's checked here; the blank-name rule belongs to the pet itself.
        """
        self._check_name_free(name, pet)
        pet.update_details(name, species)

    def _check_name_free(self, name: str, pet: Pet) -> None:
        """Raise ValueError if another pet already answers to this name.

        Tasks are assigned by picking a pet out of a list, so two pets called
        "Mochi" leave no way to say which one a task belongs to. Comparison
        ignores case and surrounding spaces.
        """
        wanted = name.strip().lower()
        if any(other is not pet and other.name.lower() == wanted for other in self.pets):
            raise ValueError(
                f"there's already a pet called {name.strip()!r}; "
                "names must be unique so a task can say whose it is"
            )

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet, and with it that pet's tasks, from the household.

        Matches on identity rather than equality, so two pets that happen to
        share a name and species are still told apart.
        """
        self.pets = [kept for kept in self.pets if kept is not pet]

    def filter_tasks(
        self,
        pet_name: str | None = None,
        completed: bool | None = None,
        priority: str | None = None,
        preferred_block: str | None = None,
        due_on_or_before: date | None = None,
        due_after: date | None = None,
    ) -> list[Task]:
        """Every task matching all of the filters given, in the order added.

        Each filter is optional and None means "don't narrow by this", so
        filter_tasks() on its own is the same as get_all_tasks(). Filters
        combine with AND: a task has to pass every one that was given.

        pet_name and preferred_block match ignoring case and surrounding
        spaces, so "mochi" finds Mochi's tasks. completed=False means still to
        do and True means done. priority is an exact "low", "medium" or "high".

        The two date filters split a list that now runs into the future:
        due_on_or_before=today is today's work plus anything overdue, and
        due_after=today is what's queued for later.

        Returns a new list; the tasks in it are the live objects, not copies.
        """
        tasks = self.get_all_tasks()

        if pet_name is not None:
            wanted = pet_name.strip().lower()
            tasks = [t for t in tasks if t.pet is not None and t.pet.name.lower() == wanted]
        if completed is not None:
            tasks = [t for t in tasks if t.completed is completed]
        if priority is not None:
            tasks = [t for t in tasks if t.priority == priority]
        if preferred_block is not None:
            wanted = preferred_block.strip().lower()
            tasks = [
                t
                for t in tasks
                if t.preferred_block is not None and t.preferred_block.lower() == wanted
            ]
        if due_on_or_before is not None:
            tasks = [t for t in tasks if t.due_date <= due_on_or_before]
        if due_after is not None:
            tasks = [t for t in tasks if t.due_date > due_after]

        return tasks

    def get_all_tasks(self) -> list[Task]:
        """Flatten every pet's tasks into one list, in the order added.

        Walking pet by pet would group the list by pet instead, so a task
        added last would appear in the middle. Sorting by added_order gives
        one list in the order the tasks were actually created.

        Returns all tasks, including completed ones. Callers that only want
        incomplete tasks (such as the scheduler) filter at the call site.
        """
        all_tasks: list[Task] = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return sorted(all_tasks, key=lambda task: task.added_order)


@dataclass
class TimeBlock:
    label: str
    start_time: str  # "HH:MM"
    end_time: str  # "HH:MM"

    def __post_init__(self) -> None:
        """Reject an unlabelled block, or one that ends at or before it starts."""
        # A task names its preferred block by label, so an unlabelled block is
        # a block nothing can ask for.
        if not self.label.strip():
            raise ValueError("every time block needs a label")
        self.label = self.label.strip()
        if self.duration_minutes() <= 0:
            raise ValueError(
                f"block {self.label!r} ends at or before it starts "
                f"({self.start_time} - {self.end_time})"
            )

    def duration_minutes(self) -> int:
        """How many minutes long this block is."""
        return _parse_hhmm(self.end_time) - _parse_hhmm(self.start_time)


def retarget_preferences(tasks: list[Task], old_label: str, new_label: str | None) -> int:
    """Point tasks that preferred `old_label` at `new_label`, or at nothing.

    A task names its preferred block by label, so renaming a block has to
    follow through to the tasks that referenced it - otherwise the preference
    quietly names a block that no longer exists, which the scheduler treats as
    no preference at all while the task still claims to have one. Passing None
    clears the preference, for when the block is removed outright.

    Returns how many tasks changed.
    """
    wanted = old_label.strip().lower()
    changed = 0
    for task in tasks:
        if task.preferred_block is not None and task.preferred_block.lower() == wanted:
            task.preferred_block = new_label
            changed += 1
    return changed


def validate_time_blocks(time_blocks: list[TimeBlock]) -> None:
    """Raise ValueError if the blocks share a label or cover the same minute.

    Two rules, both about the set of blocks rather than any one of them:

    Labels must be unique, because a task names its preferred block by label.
    Two blocks called "morning" make that preference ambiguous - the task
    lands in whichever one the scheduler reaches first. Comparison ignores
    case and surrounding spaces, so "Morning" and "morning " still clash.

    Blocks must not overlap. They're treated as separate pools of time, so an
    overlap would spend the same minute twice: 07:00-09:00 plus a second
    07:00-09:00 reads as four free hours and can place two tasks at 07:00. A
    block that starts exactly when another ends is fine - they touch but
    don't overlap.
    """
    seen: set[str] = set()
    for block in time_blocks:
        key = block.label.strip().lower()
        if key in seen:
            raise ValueError(
                f"two blocks are both called {block.label!r}; labels must be unique "
                "so a task can say which one it prefers"
            )
        seen.add(key)

    ordered = sorted(time_blocks, key=lambda block: _parse_hhmm(block.start_time))
    for earlier, later in zip(ordered, ordered[1:]):
        if _parse_hhmm(later.start_time) < _parse_hhmm(earlier.end_time):
            raise ValueError(
                f"{earlier.label!r} ({earlier.start_time}-{earlier.end_time}) and "
                f"{later.label!r} ({later.start_time}-{later.end_time}) overlap; "
                "availability can't count the same minute twice"
            )


@dataclass
class ScheduledTask:
    task: Task
    block_label: str
    start_time: str  # "HH:MM"


@dataclass
class Plan:
    scheduled_tasks: list[ScheduledTask] = field(default_factory=list)
    dropped_tasks: list[Task] = field(default_factory=list)
    # Warnings about tasks that landed on top of each other. Normally empty:
    # see Scheduler.find_conflicts() for why it is kept anyway.
    conflicts: list[str] = field(default_factory=list)

    def explain(self) -> str:
        """Describe what was scheduled, where, and why anything was left out."""
        total = len(self.scheduled_tasks) + len(self.dropped_tasks)
        lines = [f"Scheduled {len(self.scheduled_tasks)} of {total} tasks."]

        if self.scheduled_tasks:
            lines.append("")
            for entry in self.scheduled_tasks:
                task = entry.task
                if task.preferred_block is None:
                    reason = f"no block preference, placed in {entry.block_label}"
                elif task.preferred_block == entry.block_label:
                    reason = f"preferred block {entry.block_label!r} had room"
                else:
                    reason = (
                        f"preferred {task.preferred_block!r} was full, "
                        f"moved to {entry.block_label!r}"
                    )
                lines.append(
                    f"  {entry.start_time}  {task.title} ({_pet_name(task)}) "
                    f"- {task.priority} priority, {reason}"
                )

        if self.conflicts:
            lines.append("")
            lines.append("Conflicts:")
            for warning in self.conflicts:
                lines.append(f"  {warning}")

        if self.dropped_tasks:
            lines.append("")
            lines.append("Dropped - no block had enough time left:")
            for task in self.dropped_tasks:
                lines.append(
                    f"  {task.title} ({_pet_name(task)}) "
                    f"- needs {task.duration_minutes} min, {task.priority} priority"
                )

        return "\n".join(lines)


def _pet_name(task: Task) -> str:
    """Name of the pet a task belongs to, or "unassigned" if it has none."""
    return task.pet.name if task.pet is not None else "unassigned"


class Scheduler:
    """Turns a flat list of tasks plus the owner's availability into a Plan.

    Deliberately knows nothing about Owner or Pet: it takes the tasks it is
    given, so how they were gathered can change without touching this class.
    """

    def build_plan(self, tasks: list[Task], time_blocks: list[TimeBlock]) -> Plan:
        """Pack tasks into the available blocks, highest priority first.

        Tasks that fit nowhere are dropped rather than overflowing a block.
        Raises ValueError if the blocks overlap: the check lives here so no
        caller can skip it and get a plan built on double-counted time.
        """
        validate_time_blocks(time_blocks)

        minutes_used = [0] * len(time_blocks)
        scheduled: list[ScheduledTask] = []
        dropped: list[Task] = []

        for task in self.sort_tasks(tasks):
            index = self._find_block(task, time_blocks, minutes_used)
            if index is None:
                dropped.append(task)
                continue

            block = time_blocks[index]
            start = _parse_hhmm(block.start_time) + minutes_used[index]
            scheduled.append(ScheduledTask(task, block.label, _format_hhmm(start)))
            minutes_used[index] += task.duration_minutes

        # Tasks were placed in priority order; show them in clock order.
        in_order = self.sort_by_time(scheduled)
        return Plan(
            scheduled_tasks=in_order,
            dropped_tasks=dropped,
            conflicts=self.find_conflicts(in_order),
        )

    def find_conflicts(self, scheduled: list[ScheduledTask]) -> list[str]:
        """Warning messages for any two entries whose times overlap.

        Returns messages instead of raising: a double-booked morning is
        something to tell the owner about, not a reason to throw away the rest
        of a working plan. An empty list means the plan is clean.

        As things stand this should always come back empty - blocks can't
        overlap and tasks are packed one after another inside a block, so
        nothing can share a minute. It is a check on that promise rather than
        a fix for a known bug: if a later change lets two tasks land on the
        same time, the plan says so instead of quietly double-booking.

        Tasks that merely touch - one ending at 07:30 as the next starts - are
        not a conflict.

        Entries are sorted by start time and compared pairwise. Because of the
        sort, the inner loop stops at the first entry that starts after the
        current one ends, so a clean plan costs close to a single pass; the
        worst case, where everything overlaps, is quadratic. Every overlapping
        pair gets its own message, worded differently when both tasks belong
        to the same pet ("Mochi is booked twice") and when they don't ("Two
        tasks want the same minutes") - one owner can't do both at once either
        way.
        """
        warnings: list[str] = []
        in_order = self.sort_by_time(scheduled)

        for index, earlier in enumerate(in_order):
            earlier_start = _parse_hhmm(earlier.start_time)
            earlier_end = earlier_start + earlier.task.duration_minutes

            for later in in_order[index + 1 :]:
                later_start = _parse_hhmm(later.start_time)
                if later_start >= earlier_end:
                    # Sorted by start time, so nothing after this one can
                    # overlap `earlier` either.
                    break

                span = (
                    f"{earlier.task.title!r} ({_pet_name(earlier.task)}) "
                    f"{earlier.start_time}-{_format_hhmm(earlier_end)} overlaps "
                    f"{later.task.title!r} ({_pet_name(later.task)}) "
                    f"{later.start_time}-"
                    f"{_format_hhmm(later_start + later.task.duration_minutes)}"
                )
                if earlier.task.pet is not None and earlier.task.pet is later.task.pet:
                    warnings.append(f"{_pet_name(earlier.task)} is booked twice: {span}")
                else:
                    warnings.append(f"Two tasks want the same minutes: {span}")

        return warnings

    def sort_by_time(self, scheduled: list[ScheduledTask]) -> list[ScheduledTask]:
        """Scheduled tasks in clock order, earliest first.

        sorted() takes a `key` function - here a lambda returning the value to
        compare each entry by. Start times are zero-padded "HH:MM" strings, so
        comparing them as plain text gives the same answer as comparing the
        clock: "07:05" sorts before "17:30" character by character. The zero
        padding is what makes that safe; an unpadded "7:05" would sort after
        "17:30" because "7" is greater than "1".

        Returns a new list and leaves the original alone. The sort is stable,
        so entries with the same start time keep the order they came in.
        """
        return sorted(scheduled, key=lambda entry: entry.start_time)

    def sort_by_duration(self, tasks: list[Task], descending: bool = False) -> list[Task]:
        """Tasks by how long they take, shortest first unless descending.

        Uses the same sorted()-with-a-lambda-key idea as sort_by_time, keyed on
        duration_minutes. Returns a new list and leaves the original alone;
        tasks of equal length keep the order they were given in, in either
        direction.
        """
        return sorted(tasks, key=lambda task: task.duration_minutes, reverse=descending)

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Highest priority first, shorter tasks first within the same priority.

        The duration tie-break is a placeholder rule (see diagrams/uml.mmd); it
        mainly keeps the ordering deterministic so tests are stable.
        """
        return sorted(
            tasks,
            key=lambda task: (-PRIORITY_ORDER[task.priority], task.duration_minutes),
        )

    def _find_block(
        self, task: Task, time_blocks: list[TimeBlock], minutes_used: list[int]
    ) -> int | None:
        """Index of the block this task should go in, or None if it fits nowhere.

        A task's preferred block wins when it still has room. Otherwise the task
        falls back to the first block with room — preferred_block is a
        preference, not a hard constraint.
        """

        def has_room(index: int) -> bool:
            """Whether the block at this index still has time for the task."""
            remaining = time_blocks[index].duration_minutes() - minutes_used[index]
            return remaining >= task.duration_minutes

        if task.preferred_block is not None:
            for index, block in enumerate(time_blocks):
                if block.label == task.preferred_block and has_room(index):
                    return index

        for index in range(len(time_blocks)):
            if has_room(index):
                return index

        return None
