"""Tests for PawPal+ core behaviors."""

from datetime import date, timedelta

import pytest

from pawpal_system import (
    Owner,
    Pet,
    ScheduledTask,
    Scheduler,
    Task,
    TimeBlock,
    retarget_preferences,
    validate_time_blocks,
)


def test_mark_complete_changes_task_status():
    """A task starts incomplete and becomes complete when marked."""
    task = Task("Morning walk", 30, "high")

    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_add_task_increases_pet_task_count():
    """Each task added to a pet shows up in that pet's task list."""
    pet = Pet("Mochi", "dog")

    assert len(pet.tasks) == 0

    pet.add_task(Task("Morning walk", 30, "high"))
    assert len(pet.tasks) == 1

    pet.add_task(Task("Breakfast", 10, "high"))
    assert len(pet.tasks) == 2


def test_blocks_must_have_unique_labels():
    """A task names its preferred block by label, so labels can't repeat."""
    morning = TimeBlock("morning", "07:00", "09:00")

    with pytest.raises(ValueError, match="unique"):
        validate_time_blocks([morning, TimeBlock("morning", "17:30", "19:00")])

    # Case and stray spaces don't make a label distinct.
    with pytest.raises(ValueError, match="unique"):
        validate_time_blocks([morning, TimeBlock("  Morning ", "17:30", "19:00")])

    validate_time_blocks([morning, TimeBlock("evening", "17:30", "19:00")])


def test_a_block_needs_a_label():
    """An unlabelled block is one no task could ever ask for."""
    with pytest.raises(ValueError, match="label"):
        TimeBlock("   ", "07:00", "09:00")

    assert TimeBlock("  morning  ", "07:00", "09:00").label == "morning"


def test_next_occurrence_steps_the_due_date_by_frequency():
    """Daily moves a day, weekly moves a week, a one-off has no next."""
    monday = date(2026, 10, 19)

    daily = Task("Feed Mochi", 5, "high", frequency="daily", due_date=monday)
    weekly = Task("Bath", 45, "low", frequency="weekly", due_date=monday)
    once = Task("Vet visit", 60, "high", due_date=monday)

    assert daily.next_occurrence().due_date == monday + timedelta(days=1)
    assert weekly.next_occurrence().due_date == monday + timedelta(days=7)
    assert once.next_occurrence() is None

    # The next one carries the details over and starts out incomplete.
    follow_up = daily.next_occurrence()
    assert (follow_up.title, follow_up.duration_minutes, follow_up.priority) == (
        "Feed Mochi",
        5,
        "high",
    )
    assert follow_up.frequency == "daily"
    assert follow_up.completed is False
    assert follow_up is not daily


def test_an_unknown_frequency_is_rejected():
    """Same check on creation and on edit, like the other task fields."""
    with pytest.raises(ValueError, match="frequency"):
        Task("Feed Mochi", 5, "high", frequency="fortnightly")

    task = Task("Feed Mochi", 5, "high", frequency="daily")
    with pytest.raises(ValueError, match="frequency"):
        task.update_details("Feed Mochi", 5, "high", frequency="hourly")
    assert task.frequency == "daily"


def test_completing_a_repeating_task_queues_the_next_one():
    """The pet's list gains tomorrow's occurrence; a one-off adds nothing."""
    monday = date(2026, 10, 19)
    pet = Pet("Mochi", "dog")
    daily = Task("Feed Mochi", 5, "high", frequency="daily", due_date=monday)
    once = Task("Vet visit", 60, "high", due_date=monday)
    pet.add_task(daily)
    pet.add_task(once)

    follow_up = pet.complete_task(daily)

    assert daily.completed is True
    assert follow_up in pet.tasks
    assert follow_up.due_date == monday + timedelta(days=1)
    assert follow_up.pet is pet

    assert pet.complete_task(once) is None
    assert len(pet.tasks) == 3


def test_completing_twice_does_not_queue_a_second_copy():
    """Clicking Mark done on an already-done task is harmless."""
    pet = Pet("Mochi", "dog")
    daily = Task("Feed Mochi", 5, "high", frequency="daily")
    pet.add_task(daily)

    first = pet.complete_task(daily)
    second = pet.complete_task(daily)

    assert first is second
    assert len(pet.tasks) == 2


def test_undo_withdraws_the_queued_occurrence():
    """Undoing a completion takes back what the completion created."""
    pet = Pet("Mochi", "dog")
    daily = Task("Feed Mochi", 5, "high", frequency="daily")
    pet.add_task(daily)
    follow_up = pet.complete_task(daily)

    withdrawn = pet.uncomplete_task(daily)

    assert withdrawn is follow_up
    assert pet.tasks == [daily]
    assert daily.completed is False
    assert daily.spawned is None


def test_undo_keeps_a_queued_occurrence_that_has_been_touched():
    """Once the next one has been edited or done, it's the user's to keep."""
    pet = Pet("Mochi", "dog")
    daily = Task("Feed Mochi", 5, "high", frequency="daily")
    pet.add_task(daily)
    follow_up = pet.complete_task(daily)
    follow_up.update_details("Feed Mochi twice", 10, "high", frequency="daily")

    assert pet.uncomplete_task(daily) is None
    assert follow_up in pet.tasks
    assert daily.completed is False

    # Same for one that has been completed in its own right.
    other = Task("Brush", 10, "low", frequency="daily")
    pet.add_task(other)
    queued = pet.complete_task(other)
    queued.mark_complete()

    assert pet.uncomplete_task(other) is None
    assert queued in pet.tasks


def test_filter_tasks_splits_today_from_what_is_queued():
    """The date filters separate today's work from later occurrences."""
    monday = date(2026, 10, 19)
    owner = Owner("Jordan Rivera")
    pet = Pet("Mochi", "dog")
    owner.add_pet(pet)

    yesterday = Task("Missed walk", 30, "high", due_date=monday - timedelta(days=1))
    today = Task("Feed Mochi", 5, "high", frequency="daily", due_date=monday)
    tomorrow = Task("Feed Mochi", 5, "high", frequency="daily", due_date=monday + timedelta(days=1))
    for task in (yesterday, today, tomorrow):
        pet.add_task(task)

    assert owner.filter_tasks(due_on_or_before=monday) == [yesterday, today]
    assert owner.filter_tasks(due_after=monday) == [tomorrow]
    assert len(owner.filter_tasks()) == 3


def test_find_conflicts_warns_instead_of_raising():
    """Overlapping entries come back as messages; the plan still stands."""
    scheduler = Scheduler()
    mochi = Pet("Mochi", "dog")
    biscuit = Pet("Biscuit", "cat")
    walk = Task("Morning walk", 30, "high")
    brush = Task("Brushing", 15, "low")
    feed = Task("Feed Biscuit", 10, "high")
    mochi.add_task(walk)
    mochi.add_task(brush)
    biscuit.add_task(feed)

    # Same pet, overlapping times.
    warnings = scheduler.find_conflicts(
        [ScheduledTask(walk, "morning", "07:00"), ScheduledTask(brush, "morning", "07:15")]
    )
    assert len(warnings) == 1
    assert "Mochi is booked twice" in warnings[0]
    assert "07:00-07:30" in warnings[0] and "07:15-07:30" in warnings[0]

    # Different pets still clash: the owner only has one pair of hands.
    warnings = scheduler.find_conflicts(
        [ScheduledTask(walk, "morning", "07:00"), ScheduledTask(feed, "morning", "07:20")]
    )
    assert len(warnings) == 1
    assert "same minutes" in warnings[0]

    # Every overlapping pair is reported, not just the first.
    assert (
        len(
            scheduler.find_conflicts(
                [
                    ScheduledTask(walk, "morning", "07:00"),
                    ScheduledTask(brush, "morning", "07:15"),
                    ScheduledTask(feed, "morning", "07:20"),
                ]
            )
        )
        == 3
    )


def test_back_to_back_tasks_are_not_a_conflict():
    """One ending exactly as the next begins is a full morning, not a clash."""
    pet = Pet("Mochi", "dog")
    walk = Task("Morning walk", 30, "high")
    brush = Task("Brushing", 15, "low")
    pet.add_task(walk)
    pet.add_task(brush)

    entries = [
        ScheduledTask(walk, "morning", "07:00"),
        ScheduledTask(brush, "morning", "07:30"),
    ]

    assert Scheduler().find_conflicts(entries) == []
    # Order of the list doesn't matter either.
    assert Scheduler().find_conflicts(list(reversed(entries))) == []


def test_build_plan_produces_a_plan_with_no_conflicts():
    """The packing rules mean a built plan never double-books."""
    blocks = [TimeBlock("morning", "07:00", "09:00")]
    pet = Pet("Mochi", "dog")
    tasks = [
        Task("Morning walk", 30, "high", preferred_block="morning"),
        Task("Breakfast", 10, "high", preferred_block="morning"),
        Task("Brushing", 15, "low", preferred_block="morning"),
    ]
    for task in tasks:
        pet.add_task(task)

    plan = Scheduler().build_plan(tasks, blocks)

    assert len(plan.scheduled_tasks) == 3
    assert plan.conflicts == []
    assert "Conflicts" not in plan.explain()


def test_sort_by_time_puts_scheduled_tasks_in_clock_order():
    """Entries come back earliest-first however they were added."""
    blocks = [
        TimeBlock("morning", "07:00", "09:00"),
        TimeBlock("evening", "17:30", "19:00"),
    ]
    # Added out of order on purpose: the evening task first.
    tasks = [
        Task("Evening walk", 25, "medium", preferred_block="evening"),
        Task("Morning walk", 30, "high", preferred_block="morning"),
        Task("Breakfast", 10, "high", preferred_block="morning"),
    ]

    plan = Scheduler().build_plan(tasks, blocks)
    times = [entry.start_time for entry in plan.scheduled_tasks]

    assert times == sorted(times)
    assert times[0] < times[-1]
    assert [entry.task.title for entry in plan.scheduled_tasks][-1] == "Evening walk"


def test_sort_by_time_is_not_fooled_by_afternoon_times():
    """String order matches clock order because "HH:MM" is zero-padded."""
    entries = [
        ScheduledTask(Task("Evening walk", 25, "medium"), "evening", "17:30"),
        ScheduledTask(Task("Breakfast", 10, "high"), "morning", "07:05"),
        ScheduledTask(Task("Lunch", 10, "low"), "midday", "09:45"),
    ]

    in_order = Scheduler().sort_by_time(entries)

    assert [entry.start_time for entry in in_order] == ["07:05", "09:45", "17:30"]
    # sorted() returns a new list; the caller's list is untouched.
    assert entries[0].start_time == "17:30"


def test_sort_by_duration_runs_both_ways():
    """Shortest first by default, longest first when asked."""
    short = Task("Water bowl", 5, "low")
    medium = Task("Brushing", 15, "low")
    long = Task("Morning walk", 30, "high")
    tasks = [medium, long, short]

    scheduler = Scheduler()

    assert scheduler.sort_by_duration(tasks) == [short, medium, long]
    assert scheduler.sort_by_duration(tasks, descending=True) == [long, medium, short]
    assert tasks == [medium, long, short]


def test_filter_tasks_narrows_by_pet_status_priority_and_block():
    """Each filter is optional, and several of them combine."""
    owner = Owner("Jordan Rivera")
    mochi = Pet("Mochi", "dog")
    biscuit = Pet("Biscuit", "cat")
    owner.add_pet(mochi)
    owner.add_pet(biscuit)

    walk = Task("Morning walk", 30, "high", preferred_block="morning")
    brush = Task("Brushing", 15, "low")
    feed = Task("Feed Biscuit", 5, "high", preferred_block="morning")
    mochi.add_task(walk)
    mochi.add_task(brush)
    biscuit.add_task(feed)
    feed.mark_complete()

    # No filters at all is the whole list, in the order added.
    assert owner.filter_tasks() == [walk, brush, feed]

    assert owner.filter_tasks(pet_name="Mochi") == [walk, brush]
    assert owner.filter_tasks(pet_name="mochi") == [walk, brush]  # case doesn't matter
    assert owner.filter_tasks(completed=False) == [walk, brush]
    assert owner.filter_tasks(completed=True) == [feed]
    assert owner.filter_tasks(priority="high") == [walk, feed]
    assert owner.filter_tasks(preferred_block="morning") == [walk, feed]

    # Filters combine, and an impossible combination comes back empty.
    assert owner.filter_tasks(pet_name="Mochi", priority="high") == [walk]
    assert owner.filter_tasks(pet_name="Biscuit", completed=False) == []


def test_overlapping_blocks_are_rejected_but_touching_ones_are_fine():
    """Two blocks can't cover the same minute; back-to-back blocks can."""
    morning = TimeBlock("morning", "07:00", "09:00")

    with pytest.raises(ValueError, match="overlap"):
        validate_time_blocks([morning, TimeBlock("second morning", "07:00", "09:00")])

    with pytest.raises(ValueError, match="overlap"):
        validate_time_blocks([morning, TimeBlock("late start", "08:30", "10:00")])

    # Order of the list shouldn't matter.
    with pytest.raises(ValueError, match="overlap"):
        validate_time_blocks([TimeBlock("early", "06:00", "08:00"), morning])

    # Touching at 09:00 and a clearly separate evening block are both fine.
    validate_time_blocks([morning, TimeBlock("midday", "09:00", "11:00")])
    validate_time_blocks([morning, TimeBlock("evening", "17:30", "19:00")])


def test_build_plan_refuses_to_schedule_against_overlapping_blocks():
    """The scheduler enforces the rule itself, so no caller can skip it."""
    blocks = [TimeBlock("morning", "07:00", "09:00"), TimeBlock("again", "07:00", "09:00")]

    with pytest.raises(ValueError, match="overlap"):
        Scheduler().build_plan([Task("Morning walk", 30, "high")], blocks)


def test_update_details_edits_a_task_but_rejects_bad_details():
    """An edit applies the same checks as construction, all-or-nothing."""
    task = Task("Morning walk", 30, "high")

    task.update_details("Evening walk", 45, "low", preferred_block="evening")

    assert (task.title, task.duration_minutes, task.priority) == ("Evening walk", 45, "low")
    assert task.preferred_block == "evening"

    for bad in [("  ", 45, "low"), ("Walk", 0, "low"), ("Walk", 45, "urgent")]:
        with pytest.raises(ValueError):
            task.update_details(*bad)

    # A rejected edit leaves the task exactly as it was.
    assert (task.title, task.duration_minutes, task.priority) == ("Evening walk", 45, "low")


def test_update_details_leaves_completion_and_pet_alone():
    """Editing what a task is doesn't change who owns it or whether it's done."""
    pet = Pet("Mochi", "dog")
    task = Task("Morning walk", 30, "high")
    pet.add_task(task)
    task.mark_complete()

    task.update_details("Short walk", 10, "low")

    assert task.completed is True
    assert task.pet is pet


def test_remove_task_drops_only_that_task():
    """Removal matches on identity, so an identical-looking task stays."""
    pet = Pet("Mochi", "dog")
    first = Task("Morning walk", 30, "high")
    twin = Task("Morning walk", 30, "high")
    pet.add_task(first)
    pet.add_task(twin)

    pet.remove_task(first)

    assert len(pet.tasks) == 1
    assert pet.tasks[0] is twin


def test_update_details_renames_a_pet_but_rejects_a_blank_name():
    """Editing a pet trims the new values; an empty name is refused."""
    pet = Pet("Mochi", "dog")

    pet.update_details("  Mochi Jr  ", "  shiba inu  ")

    assert (pet.name, pet.species) == ("Mochi Jr", "shiba inu")

    with pytest.raises(ValueError):
        pet.update_details("   ", "dog")

    assert pet.name == "Mochi Jr"


def test_remove_pet_drops_only_that_pet_and_its_tasks():
    """Removing one pet takes its tasks and leaves the other pet untouched."""
    owner = Owner("Jordan Rivera")
    mochi = Pet("Mochi", "dog")
    biscuit = Pet("Biscuit", "cat")
    mochi.add_task(Task("Morning walk", 30, "high"))
    biscuit.add_task(Task("Litter box", 10, "medium"))
    owner.add_pet(mochi)
    owner.add_pet(biscuit)

    owner.remove_pet(mochi)

    assert owner.pets == [biscuit]
    assert [task.title for task in owner.get_all_tasks()] == ["Litter box"]


def test_pet_names_must_be_unique_within_a_household():
    """Tasks are assigned by picking a pet, so two "Mochi"s are ambiguous."""
    owner = Owner("Jordan Rivera")
    mochi = Pet("Mochi", "dog")
    owner.add_pet(mochi)

    with pytest.raises(ValueError, match="unique"):
        owner.add_pet(Pet("Mochi", "cat"))

    # Case and stray spaces don't make a name distinct.
    with pytest.raises(ValueError, match="unique"):
        owner.add_pet(Pet("  MOCHI ", "cat"))

    biscuit = Pet("Biscuit", "cat")
    owner.add_pet(biscuit)

    with pytest.raises(ValueError, match="unique"):
        owner.update_pet(biscuit, "Mochi", "cat")

    # A pet doesn't clash with itself, so editing only the species is fine.
    owner.update_pet(mochi, "Mochi", "shiba inu")
    assert mochi.species == "shiba inu"
    assert [pet.name for pet in owner.pets] == ["Mochi", "Biscuit"]


def test_owner_and_pet_names_cannot_be_blank():
    """The household and everyone in it needs a name."""
    with pytest.raises(ValueError, match="owner name"):
        Owner("   ")

    owner = Owner("  Jordan Rivera  ")
    assert owner.name == "Jordan Rivera"

    with pytest.raises(ValueError, match="pet name"):
        Pet("  ", "dog")

    with pytest.raises(ValueError, match="owner name"):
        owner.rename(" ")
    assert owner.name == "Jordan Rivera"


def test_retarget_preferences_follows_a_renamed_or_removed_block():
    """A preference tracks its block instead of pointing at a stale label."""
    walk = Task("Morning walk", 30, "high", preferred_block="morning")
    brush = Task("Brushing", 10, "low", preferred_block="Morning")
    evening = Task("Evening walk", 20, "medium", preferred_block="evening")
    free = Task("Water bowl", 5, "low")
    tasks = [walk, brush, evening, free]

    assert retarget_preferences(tasks, "morning", "early") == 2
    assert walk.preferred_block == "early"
    assert brush.preferred_block == "early"
    assert evening.preferred_block == "evening"
    assert free.preferred_block is None

    # Removing a block clears the preferences that named it.
    assert retarget_preferences(tasks, "early", None) == 2
    assert walk.preferred_block is None
    assert brush.preferred_block is None
