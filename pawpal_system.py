"""PawPal+ class stubs — generated from diagrams/uml.mmd.

No scheduling logic yet. This is step 3 of the suggested workflow in README.md:
convert the UML into class stubs before implementing behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low" | "medium" | "high"
    preferred_block: str | None = None  # TimeBlock.label; a preference, not a hard constraint
    completed: bool = False
    pet: "Pet | None" = None  # back-reference, set by Pet.add_task()


@dataclass
class Pet:
    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        raise NotImplementedError


@dataclass
class Owner:
    name: str
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        raise NotImplementedError

    def get_all_tasks(self) -> list[Task]:
        raise NotImplementedError


@dataclass
class TimeBlock:
    label: str
    start_time: str  # "HH:MM"
    end_time: str  # "HH:MM"

    def duration_minutes(self) -> int:
        raise NotImplementedError


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
        raise NotImplementedError


class Scheduler:
    def build_plan(self, tasks: list[Task], time_blocks: list[TimeBlock]) -> Plan:
        raise NotImplementedError

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        raise NotImplementedError
