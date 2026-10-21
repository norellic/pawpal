"""Temporary CLI testing ground for PawPal+.

Builds a sample household and prints today's tasks, so the backend logic can be
verified in the terminal before any of it is wired into the Streamlit UI.

Run with:  python main.py
"""

from pawpal_system import Owner, Pet, Scheduler, Task, TimeBlock


def build_sample_household() -> Owner:
    """Create a sample owner with two pets and a handful of tasks."""
    owner = Owner(name="Jordan Rivera")

    mochi = Pet(name="Mochi", species="dog")
    biscuit = Pet(name="Biscuit", species="cat")
    owner.add_pet(mochi)
    owner.add_pet(biscuit)

    mochi.add_task(Task("Morning walk", 30, "high", preferred_block="morning"))
    mochi.add_task(Task("Breakfast", 10, "high", preferred_block="morning"))
    mochi.add_task(Task("Evening walk", 25, "medium", preferred_block="evening"))
    mochi.add_task(Task("Brushing", 15, "low"))

    biscuit.add_task(Task("Feed Biscuit", 5, "high", preferred_block="morning"))
    biscuit.add_task(Task("Litter box", 10, "medium"))
    biscuit.add_task(Task("Puzzle toy", 20, "low", preferred_block="evening"))

    return owner


def build_sample_day() -> list[TimeBlock]:
    """The owner's availability for today: a morning window and an evening window."""
    return [
        TimeBlock(label="morning", start_time="07:00", end_time="09:00"),
        TimeBlock(label="evening", start_time="17:30", end_time="19:00"),
    ]


def print_tasks(owner: Owner) -> None:
    """Print every task across all pets, grouped by pet."""
    print(f"Today's Tasks for {owner.name}")
    print("=" * 52)

    for pet in owner.pets:
        print(f"\n{pet.name} ({pet.species})")
        for task in pet.tasks:
            block = task.preferred_block or "any"
            print(
                f"  - {task.title:<14} {task.duration_minutes:>3} min"
                f"  [{task.priority:<6}] prefers: {block}"
            )

    all_tasks = owner.get_all_tasks()
    total_minutes = sum(task.duration_minutes for task in all_tasks)
    print(f"\n{len(all_tasks)} tasks, {total_minutes} minutes of care needed today.")


def print_schedule(owner: Owner, time_blocks: list[TimeBlock]) -> None:
    """Build and print today's plan."""
    # Completed tasks are filtered here rather than inside get_all_tasks(), so
    # other callers (history views, the UI) can still see the full list.
    todo = [task for task in owner.get_all_tasks() if not task.completed]

    available = sum(block.duration_minutes() for block in time_blocks)
    plan = Scheduler().build_plan(todo, time_blocks)

    print(f"\nToday's Schedule ({available} minutes available)")
    print("=" * 52)
    print(plan.explain())


def main() -> None:
    owner = build_sample_household()
    time_blocks = build_sample_day()

    print_tasks(owner)

    print("\nAvailability")
    print("=" * 52)
    for block in time_blocks:
        print(f"  {block.label:<8} {block.start_time} - {block.end_time}")

    print_schedule(owner, time_blocks)


if __name__ == "__main__":
    main()
