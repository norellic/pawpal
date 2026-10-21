"""Temporary CLI testing ground for PawPal+.

Builds a sample household and prints today's tasks, so the backend logic can be
verified in the terminal before any of it is wired into the Streamlit UI.

Run with:  python main.py
"""

from datetime import date, timedelta

from pawpal_system import Owner, Pet, ScheduledTask, Scheduler, Task, TimeBlock

TODAY = date.today()


def build_sample_household() -> Owner:
    """Create a sample owner with two pets and a handful of tasks.

    Tasks are deliberately added out of clock order - an evening walk before a
    morning one - so the sorting below has something real to do.
    """
    owner = Owner(name="Jordan Rivera")

    mochi = Pet(name="Mochi", species="dog")
    biscuit = Pet(name="Biscuit", species="cat")
    owner.add_pet(mochi)
    owner.add_pet(biscuit)

    mochi.add_task(Task("Evening walk", 25, "medium", preferred_block="evening"))
    mochi.add_task(
        Task("Morning walk", 30, "high", preferred_block="morning", frequency="daily")
    )
    mochi.add_task(Task("Brushing", 15, "low", frequency="weekly"))
    mochi.add_task(Task("Breakfast", 10, "high", preferred_block="morning"))

    biscuit.add_task(Task("Puzzle toy", 20, "low", preferred_block="evening"))
    biscuit.add_task(
        Task("Feed Biscuit", 5, "high", preferred_block="morning", frequency="daily")
    )
    biscuit.add_task(Task("Litter box", 10, "medium"))

    # One task already done, so the status filter has both kinds to sort out.
    biscuit.tasks[1].mark_complete()

    return owner


def build_sample_day() -> list[TimeBlock]:
    """The owner's availability for today: a morning window and an evening window."""
    return [
        TimeBlock(label="morning", start_time="07:00", end_time="09:00"),
        TimeBlock(label="evening", start_time="17:30", end_time="19:00"),
    ]


def describe(task: Task) -> str:
    """One task as a single line."""
    pet = task.pet.name if task.pet else "unassigned"
    status = "done" if task.completed else "to do"
    block = task.preferred_block or "any"
    return (
        f"  - {task.title:<14} {task.duration_minutes:>3} min"
        f"  [{task.priority:<6}] {pet:<8} {status:<5} {task.frequency:<6}"
        f" due {task.due_date:%a %d %b}  prefers: {block}"
    )


def print_recurrence(owner: Owner) -> None:
    """Complete a daily and a weekly task, and show what gets queued next.

    The UI can't demonstrate this well - tomorrow never arrives while the app
    is open - but here the dates speak for themselves.
    """
    print("\nRecurrence")
    print("=" * 72)

    mochi, biscuit = owner.pets
    walk = next(t for t in mochi.tasks if t.title == "Morning walk")  # daily
    brushing = next(t for t in mochi.tasks if t.title == "Brushing")  # weekly
    breakfast = next(t for t in mochi.tasks if t.title == "Breakfast")  # one-off

    for task in (walk, brushing, breakfast):
        follow_up = mochi.complete_task(task)
        if follow_up is None:
            print(f"  {task.title:<14} {task.frequency:<6} -> nothing queued, it was a one-off")
        else:
            print(
                f"  {task.title:<14} {task.frequency:<6} -> next one due "
                f"{follow_up.due_date:%a %d %b} "
                f"({(follow_up.due_date - task.due_date).days} day(s) later)"
            )

    assert walk.spawned is not None and walk.spawned.due_date == TODAY + timedelta(days=1)
    assert brushing.spawned is not None and brushing.spawned.due_date == TODAY + timedelta(days=7)

    print("\n  Completing the same task twice doesn't queue a second copy:")
    before = len(mochi.tasks)
    mochi.complete_task(walk)
    print(f"    Mochi had {before} tasks, still has {len(mochi.tasks)}")

    print("\n  Undo takes the queued occurrence back:")
    withdrawn = mochi.uncomplete_task(walk)
    print(f"    withdrew {withdrawn.title} due {withdrawn.due_date:%a %d %b}")
    print(f"    Mochi now has {len(mochi.tasks)} tasks, walk completed={walk.completed}")

    print("\n  Queued for later (not part of today's plan):")
    for task in owner.filter_tasks(due_after=TODAY):
        print(describe(task))


def print_tasks(owner: Owner) -> None:
    """Print every task across all pets, in the order they were added."""
    print(f"Today's Tasks for {owner.name}")
    print("=" * 72)

    all_tasks = owner.get_all_tasks()
    for task in all_tasks:
        print(describe(task))

    total_minutes = sum(task.duration_minutes for task in all_tasks)
    print(f"\n{len(all_tasks)} tasks, {total_minutes} minutes of care needed today.")


def print_filters(owner: Owner) -> None:
    """Show filter_tasks() narrowing the list by pet, status, and priority."""
    print("\nFiltering")
    print("=" * 72)

    print("Mochi's tasks only:")
    for task in owner.filter_tasks(pet_name="Mochi"):
        print(describe(task))

    print("\nStill to do:")
    for task in owner.filter_tasks(completed=False):
        print(describe(task))

    print("\nAlready done:")
    for task in owner.filter_tasks(completed=True):
        print(describe(task))

    print("\nBiscuit's high-priority tasks (filters combine):")
    for task in owner.filter_tasks(pet_name="Biscuit", priority="high"):
        print(describe(task))

    print("\nAnything wanting the morning block:")
    for task in owner.filter_tasks(preferred_block="morning"):
        print(describe(task))


def print_sorted(owner: Owner) -> None:
    """Show sort_by_duration() in both directions."""
    scheduler = Scheduler()
    print("\nSorting by duration")
    print("=" * 72)

    print("Shortest first:")
    for task in scheduler.sort_by_duration(owner.get_all_tasks()):
        print(describe(task))

    print("\nLongest first:")
    for task in scheduler.sort_by_duration(owner.get_all_tasks(), descending=True):
        print(describe(task))


def print_conflicts() -> None:
    """Put two tasks on the same minutes and check the Scheduler says so.

    build_plan() packs tasks one after another inside a block and blocks are
    not allowed to overlap, so a plan it builds has nothing to find. These
    entries are assembled by hand to prove the check actually fires.
    """
    scheduler = Scheduler()
    mochi = Pet("Mochi", "dog")
    biscuit = Pet("Biscuit", "cat")

    walk = Task("Morning walk", 30, "high")
    brush = Task("Brushing", 15, "low")
    feed = Task("Feed Biscuit", 10, "high")
    mochi.add_task(walk)
    mochi.add_task(brush)
    biscuit.add_task(feed)

    print("\nConflict detection")
    print("=" * 72)

    # Same pet, same time: 07:00-07:30 against 07:15-07:30.
    same_pet = [
        ScheduledTask(walk, "morning", "07:00"),
        ScheduledTask(brush, "morning", "07:15"),
    ]
    # A second pet wanting the same minutes is a conflict too - the owner
    # only has one pair of hands.
    both_pets = same_pet + [ScheduledTask(feed, "morning", "07:20")]
    # Back to back is fine: brushing starts exactly as the walk ends.
    back_to_back = [
        ScheduledTask(walk, "morning", "07:00"),
        ScheduledTask(brush, "morning", "07:30"),
    ]

    for label, entries in (
        ("same pet, overlapping", same_pet),
        ("two pets, overlapping", both_pets),
        ("back to back", back_to_back),
    ):
        warnings = scheduler.find_conflicts(entries)
        print(f"\n  {label}: {len(warnings)} warning(s)")
        for warning in warnings:
            print(f"    ! {warning}")


def print_schedule(owner: Owner, time_blocks: list[TimeBlock]) -> None:
    """Build and print today's plan, in clock order."""
    # Completed tasks are filtered here rather than inside get_all_tasks(), so
    # other callers (history views, the UI) can still see the full list.
    todo = owner.filter_tasks(completed=False, due_on_or_before=TODAY)

    available = sum(block.duration_minutes() for block in time_blocks)
    plan = Scheduler().build_plan(todo, time_blocks)

    print(f"\nToday's Schedule ({available} minutes available)")
    print("=" * 72)
    # build_plan() already runs the entries through sort_by_time(), so tasks
    # added out of order still come back earliest-first.
    for entry in plan.scheduled_tasks:
        print(f"  {entry.start_time}  {entry.task.title:<14} ({entry.block_label})")

    print()
    print(plan.explain())

    # Nothing to report: blocks can't overlap and tasks are packed one after
    # another, so a plan built here never double-books.
    print(f"\n  conflicts found in this plan: {len(plan.conflicts)}")


def main() -> None:
    owner = build_sample_household()
    time_blocks = build_sample_day()

    print_tasks(owner)
    print_filters(owner)
    print_sorted(owner)
    print_recurrence(owner)

    print("\nAvailability")
    print("=" * 72)
    for block in time_blocks:
        print(f"  {block.label:<8} {block.start_time} - {block.end_time}")

    print_schedule(owner, time_blocks)
    print_conflicts()


if __name__ == "__main__":
    main()
