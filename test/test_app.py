"""Tests for the Streamlit UI, driven headlessly with Streamlit's AppTest.

These cover the behaviours that live in app.py itself rather than in the
backend classes: what a click does, and what stays on screen afterwards. They
run the real script, so they're slower than the unit tests in test_pawpal.py.
"""

from datetime import date, time, timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def new_app() -> AppTest:
    """A fresh session of the app, run once."""
    return AppTest.from_file(APP, default_timeout=30).run()


def button(at: AppTest, label: str):
    """The first button with this label."""
    return next(b for b in at.button if b.label == label)


def add_pet(at: AppTest, name: str, species: str = "dog") -> None:
    at.text_input[1].input(name)
    at.text_input[2].input(species)
    button(at, "Add pet").click().run()


def add_task(at: AppTest, title: str, frequency: str = "once") -> None:
    next(t for t in at.text_input if t.label == "Task").input(title)
    next(s for s in at.selectbox if s.label == "Repeats" and s.key is None).set_value(frequency)
    button(at, "Add task").click().run()


def tasks(at: AppTest):
    return at.session_state.owner.get_all_tasks()


def task_rows(at: AppTest) -> list[str]:
    """The rendered text of each task row."""
    return [m.value for m in at.markdown if " min " in m.value]


def test_the_app_starts_by_asking_for_a_pet():
    """With an empty household there's nothing else to show yet."""
    at = new_app()

    assert not at.exception
    assert any("Add a pet" in info.value for info in at.info)
    assert not at.button or all(b.label != "Generate schedule" for b in at.button)


def test_a_duplicate_pet_name_is_refused_with_a_message():
    """Two pets can't share a name, whatever the capitalisation."""
    at = new_app()
    add_pet(at, "Mochi")
    add_pet(at, " MOCHI ", "cat")

    assert not at.exception
    assert [pet.name for pet in at.session_state.owner.pets] == ["Mochi"]
    assert any("already a pet" in error.value for error in at.error)


def test_deleting_a_pet_asks_before_removing_it():
    """Delete shows a confirmation; only 'Yes, delete' removes the pet."""
    at = new_app()
    add_pet(at, "Mochi")

    button(at, "Delete").click().run()
    assert any("Delete Mochi" in warning.value for warning in at.warning)
    assert len(at.session_state.owner.pets) == 1

    button(at, "Yes, delete").click().run()
    assert at.session_state.owner.pets == []


def test_marking_a_daily_task_done_queues_tomorrows_in_the_app():
    """The new occurrence exists, and the Due filter files it under upcoming."""
    at = new_app()
    add_pet(at, "Mochi")
    add_task(at, "Feed Mochi", frequency="daily")

    button(at, "Mark done").click().run()

    assert not at.exception
    assert len(tasks(at)) == 2
    assert tasks(at)[1].due_date == date.today() + timedelta(days=1)
    assert any("queued" in toast.value for toast in at.toast)

    # Only today's occurrence shows by default; tomorrow's waits under upcoming.
    assert len(task_rows(at)) == 1
    next(s for s in at.selectbox if s.key == "filter-due").set_value("upcoming").run()
    assert len(task_rows(at)) == 1
    assert "due " in task_rows(at)[0]


def test_undo_takes_back_the_queued_occurrence():
    """Marking done then Undo leaves the list as it started."""
    at = new_app()
    add_pet(at, "Mochi")
    add_task(at, "Feed Mochi", frequency="daily")
    button(at, "Mark done").click().run()
    next(s for s in at.selectbox if s.key == "filter-due").set_value("all dates").run()

    button(at, "Undo").click().run()

    assert not at.exception
    assert len(tasks(at)) == 1
    assert tasks(at)[0].completed is False


def test_the_plan_stays_on_screen_after_marking_a_task_done():
    """The plan used to vanish on the next interaction; it should persist."""
    at = new_app()
    add_pet(at, "Mochi")
    add_task(at, "Walk")
    add_task(at, "Brush")

    button(at, "Generate schedule").click().run()
    assert len(at.metric) == 3

    button(at, "Mark done").click().run()

    assert not at.exception
    assert len(at.metric) == 3


def test_generating_with_no_tasks_says_there_is_nothing_to_schedule():
    """An empty list is not the same as 'everything is done'."""
    at = new_app()
    add_pet(at, "Mochi")

    button(at, "Generate schedule").click().run()

    assert any("nothing to schedule" in info.value for info in at.info)
    assert not at.success


def test_overlapping_availability_is_flagged_and_blocks_the_plan():
    """An overlapping block is an error, and Generate is withheld until fixed."""
    at = new_app()
    add_pet(at, "Mochi")

    button(at, "Add a time block").click().run()
    starts = [t for t in at.time_input if t.key and t.key.startswith("start-")]
    ends = [t for t in at.time_input if t.key and t.key.startswith("end-")]
    starts[-1].set_value(time(8, 0))
    ends[-1].set_value(time(10, 0)).run()

    assert any("overlap" in error.value for error in at.error)
    assert all(b.label != "Generate schedule" for b in at.button)

    # Moving it to start where morning ends makes the blocks touch, which is fine.
    starts = [t for t in at.time_input if t.key and t.key.startswith("start-")]
    starts[-1].set_value(time(9, 0)).run()

    assert not at.error
    assert any(b.label == "Generate schedule" for b in at.button)


def test_renaming_a_block_carries_over_to_tasks_that_preferred_it():
    """The task's preference follows the new name instead of going stale."""
    at = new_app()
    add_pet(at, "Mochi")
    next(t for t in at.text_input if t.label == "Task").input("Morning walk")
    next(s for s in at.selectbox if s.label == "Preferred time").set_value("morning")
    button(at, "Add task").click().run()

    labels = [t for t in at.text_input if t.key and t.key.startswith("label-")]
    labels[0].set_value("early").run()

    assert tasks(at)[0].preferred_block == "early"
    assert "prefers early" in task_rows(at)[0]


def test_filters_and_sort_change_what_the_list_shows():
    """Pet filter narrows, duration sort reorders, and both are reversible."""
    at = new_app()
    add_pet(at, "Mochi")
    add_pet(at, "Biscuit", "cat")

    for pet, title, minutes in (("Mochi", "Long walk", 45), ("Biscuit", "Feed", 5)):
        next(t for t in at.text_input if t.label == "Task").input(title)
        next(s for s in at.selectbox if s.label == "Pet" and s.key is None).set_value(pet)
        next(n for n in at.number_input if n.key is None).set_value(minutes)
        button(at, "Add task").click().run()

    assert len(task_rows(at)) == 2
    assert "Long walk" in task_rows(at)[0]  # order added

    next(s for s in at.selectbox if s.key == "sort-tasks").set_value("shortest first").run()
    assert "Feed" in task_rows(at)[0]

    next(s for s in at.selectbox if s.key == "filter-pet").set_value("Mochi").run()
    assert len(task_rows(at)) == 1
    assert "Long walk" in task_rows(at)[0]
