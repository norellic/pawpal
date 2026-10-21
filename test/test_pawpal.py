"""Tests for PawPal+ core behaviors."""

from pawpal_system import Pet, Task


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
