"""PawPal+ core classes, implemented from diagrams/uml.mmd.

Owner and Pet hold the data, Task is a passive record of what needs doing, and
Scheduler makes all the placement decisions. Scheduler takes a flat list of
tasks rather than an Owner, so how tasks are gathered can change without
touching the scheduling logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Priority labels, ranked most to least important. Used to validate Task.priority
# and to sort tasks in Scheduler.sort_tasks().
PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}


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


def _check_task_fields(title: str, duration_minutes: int, priority: str) -> None:
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


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low" | "medium" | "high"
    preferred_block: str | None = None  # TimeBlock.label; a preference, not a hard constraint
    completed: bool = False
    pet: Pet | None = None  # back-reference, set by Pet.add_task()

    def __post_init__(self) -> None:
        """Reject a blank title, unknown priority, or non-positive duration."""
        _check_task_fields(self.title, self.duration_minutes, self.priority)
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
    ) -> None:
        """Change this task's details, applying the same checks as construction.

        Leaves completion status and the pet back-reference alone: editing what
        a task is doesn't change who it belongs to or whether it's done.
        """
        _check_task_fields(title, duration_minutes, priority)
        self.title = title.strip()
        self.duration_minutes = duration_minutes
        self.priority = priority
        self.preferred_block = preferred_block


@dataclass
class Pet:
    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Attach a task to this pet and set the task's back-reference."""
        task.pet = self
        self.tasks.append(task)

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

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's household."""
        self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet, and with it that pet's tasks, from the household.

        Matches on identity rather than equality, so two pets that happen to
        share a name and species are still told apart.
        """
        self.pets = [kept for kept in self.pets if kept is not pet]

    def get_all_tasks(self) -> list[Task]:
        """Flatten every pet's tasks into one list.

        Returns all tasks, including completed ones. Callers that only want
        incomplete tasks (such as the scheduler) filter at the call site.
        """
        all_tasks: list[Task] = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks


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
        scheduled.sort(key=lambda entry: _parse_hhmm(entry.start_time))
        return Plan(scheduled_tasks=scheduled, dropped_tasks=dropped)

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
