"""Tests for PawPal+ core behaviors."""

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task, TimeBlock, validate_time_blocks


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
    """Removal matches on identity, so a same-named twin is left alone."""
    owner = Owner("Jordan Rivera")
    first = Pet("Mochi", "dog")
    twin = Pet("Mochi", "dog")
    first.add_task(Task("Morning walk", 30, "high"))
    owner.add_pet(first)
    owner.add_pet(twin)

    owner.remove_pet(first)

    assert owner.pets == [twin]
    assert owner.pets[0] is twin
    assert owner.get_all_tasks() == []
