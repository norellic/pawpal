"""PawPal+ Streamlit UI.

A thin bridge over pawpal_system.py: this file collects input and renders
output, but every scheduling decision is made by the backend classes.
"""

from datetime import date, time
from itertools import count

import streamlit as st

from pawpal_system import (
    FREQUENCY_STEPS,
    PRIORITY_ORDER,
    Owner,
    Pet,
    Scheduler,
    Task,
    TimeBlock,
    retarget_preferences,
    validate_time_blocks,
)

st.set_page_config(page_title="PawPal+", page_icon=":material/pets:", layout="centered")

# Pull the valid priorities from the backend so the UI can't offer a value
# Task.__post_init__ would reject.
PRIORITIES = list(PRIORITY_ORDER)
# Same idea for how often a task comes back: "once" means it never does.
FREQUENCIES = list(FREQUENCY_STEPS)
TODAY = date.today()


def due_label(task) -> str:
    """How a task's schedule reads on its row.

    Today's date is left unsaid - it's the common case and the plan is built
    for today - so a row only mentions a date when it isn't today's.
    """
    parts = []
    if task.frequency != "once":
        parts.append(task.frequency)
    if task.due_date < TODAY:
        parts.append(f"overdue from {task.due_date:%a %d %b}")
    elif task.due_date > TODAY:
        parts.append(f"due {task.due_date:%a %d %b}")
    return " · ".join(parts)


def preference_label(label: str | None) -> str:
    """How a preferred-block choice reads in a dropdown.

    No preference is the value None rather than a magic string, and it reads
    as a phrase no one would label a block, so a block can never be confused
    with "no preference" by either the code or the person reading the list.
    """
    return "no preference" if label is None else label

# --- Session state -----------------------------------------------------------
# The Owner object graph lives here, so pets, tasks, and completion status
# survive Streamlit's top-to-bottom rerun on every interaction.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan Rivera")
if "block_ids" not in st.session_state:
    # Widget keys are built from these ids rather than list positions, so
    # removing a block doesn't hand its stored widget state to its neighbour.
    st.session_state.block_ids = count()
    st.session_state.blocks = [
        {"id": next(st.session_state.block_ids), "label": "morning",
         "start": time(7, 0), "end": time(9, 0)},
        {"id": next(st.session_state.block_ids), "label": "evening",
         "start": time(17, 30), "end": time(19, 0)},
    ]

if "plan" not in st.session_state:
    # The last plan built, kept here so it survives the reruns that marking a
    # task done or editing anything else triggers. plan_inputs records what it
    # was built from, so the page can say when it no longer matches.
    st.session_state.plan = None
    st.session_state.plan_minutes = 0
    st.session_state.plan_inputs = None

if "editing_pet" not in st.session_state:
    # Which pet's card is in edit mode, which pet is waiting on a delete
    # confirmation, and which task is in edit mode. Each holds id(object) —
    # see the comment on pet_key below.
    st.session_state.editing_pet = None
    st.session_state.deleting_pet = None
    st.session_state.editing_task = None

owner: Owner = st.session_state.owner
blocks: list[dict] = st.session_state.blocks

# The availability widgets live near the bottom of the page, but the task
# forms above offer block labels to prefer. Pull each block's current widget
# value up here so those dropdowns show what the inputs say now, rather than
# what they said on the previous run.
for block in blocks:
    if f"label-{block['id']}" not in st.session_state:
        continue
    typed_label = st.session_state[f"label-{block['id']}"]
    if typed_label.strip() and typed_label.strip() != block["label"]:
        # Carry the rename over to the tasks that named the old label, so a
        # preference never points at a block that no longer exists.
        retarget_preferences(owner.get_all_tasks(), block["label"], typed_label.strip())
    block["label"] = typed_label
    block["start"] = st.session_state[f"start-{block['id']}"]
    block["end"] = st.session_state[f"end-{block['id']}"]

st.title("PawPal+")
st.caption("Plan the day's pet care around the time you actually have.")

# --- Household ---------------------------------------------------------------
st.subheader("Household")
# Keep the previous name rather than letting the household go nameless; the
# box still shows what was typed, so it's clear what needs fixing.
try:
    owner.rename(st.text_input("Owner name", value=owner.name))
except ValueError as error:
    st.error(str(error), icon=":material/error:")

with st.form("add_pet", border=True, clear_on_submit=True):
    st.markdown("**Add a pet**")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        new_pet_name = st.text_input("Pet name", placeholder="Mochi")
        # Free text rather than a fixed list, so a breed ("shiba inu") or an
        # animal the list never anticipated is just as easy to type.
        new_species = st.text_input("Species", placeholder="dog")
        pet_submitted = st.form_submit_button("Add pet", icon=":material/add:")

if pet_submitted:
    if not new_pet_name.strip():
        st.error("Give the pet a name first.")
    else:
        # No st.rerun() here: everything that shows a pet is rendered further
        # down this same run, and an extra rerun would cancel the form's
        # clear_on_submit before the emptied boxes ever reach the browser.
        try:
            owner.add_pet(Pet(name=new_pet_name, species=new_species.strip() or "pet"))
        except ValueError as error:
            st.error(str(error), icon=":material/error:")

if not owner.pets:
    st.info("Add a pet to get started.", icon=":material/pets:")
    st.stop()

st.caption(f"{owner.name} has {len(owner.pets)} pet(s).")

for pet in owner.pets:
    # Widget keys are built from the object's identity rather than its position
    # or name, so renaming or removing a pet doesn't hand its stored widget
    # state to a neighbour.
    pet_key = id(pet)
    with st.container(border=True):
        if st.session_state.editing_pet == pet_key:
            with st.form(f"edit-pet-{pet_key}", border=False):
                with st.container(horizontal=True, vertical_alignment="bottom"):
                    edited_name = st.text_input(
                        "Pet name", value=pet.name, key=f"pet-name-{pet_key}"
                    )
                    edited_species = st.text_input(
                        "Species", value=pet.species, key=f"pet-species-{pet_key}"
                    )
                    saved = st.form_submit_button("Save", icon=":material/check:")
                    cancelled = st.form_submit_button("Cancel", icon=":material/close:")

            if cancelled:
                st.session_state.editing_pet = None
                st.rerun()
            if saved:
                # The backend rejects a blank name or one another pet already
                # answers to, so surface that rather than applying it.
                try:
                    owner.update_pet(pet, edited_name, edited_species)
                except ValueError as error:
                    st.error(str(error), icon=":material/error:")
                else:
                    st.session_state.editing_pet = None
                    st.rerun()
        else:
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{pet.name}** · {pet.species} · {len(pet.tasks)} task(s)")
                if st.button("Edit", key=f"edit-pet-{pet_key}", icon=":material/edit:"):
                    # One editor at a time, whichever kind. An editor closed
                    # this way is simply abandoned: edits only reach the pet or
                    # task when Save is pressed.
                    st.session_state.editing_pet = pet_key
                    st.session_state.deleting_pet = None
                    st.session_state.editing_task = None
                    st.rerun()
                if st.button("Delete", key=f"delete-pet-{pet_key}", icon=":material/delete:"):
                    st.session_state.deleting_pet = pet_key
                    st.session_state.editing_pet = None
                    st.session_state.editing_task = None
                    st.rerun()

        if st.session_state.deleting_pet == pet_key:
            # Removing a pet takes its tasks with it, so say so and confirm.
            st.warning(
                f"Delete {pet.name} and {len(pet.tasks)} task(s)?",
                icon=":material/warning:",
            )
            with st.container(horizontal=True):
                if st.button("Yes, delete", key=f"confirm-delete-{pet_key}", type="primary"):
                    owner.remove_pet(pet)
                    st.session_state.deleting_pet = None
                    st.rerun()
                if st.button("Keep", key=f"cancel-delete-{pet_key}"):
                    st.session_state.deleting_pet = None
                    st.rerun()

# --- Tasks -------------------------------------------------------------------
st.subheader("Tasks")

with st.form("add_task", border=True):
    st.markdown("**Add a task**")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        pet_name = st.selectbox("Pet", [p.name for p in owner.pets])
        title = st.text_input("Task", placeholder="Morning walk")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        priority = st.selectbox("Priority", PRIORITIES)
        preferred = st.selectbox(
            "Preferred time",
            [None] + [b["label"] for b in blocks],
            format_func=preference_label,
        )
        frequency = st.selectbox("Repeats", FREQUENCIES)
        task_submitted = st.form_submit_button("Add task", icon=":material/add:")

if task_submitted:
    if not title.strip():
        st.error("Give the task a title first.")
    else:
        pet = next(p for p in owner.pets if p.name == pet_name)
        pet.add_task(
            Task(
                title=title.strip(),
                duration_minutes=int(duration),
                priority=priority,
                preferred_block=preferred,
                frequency=frequency,
            )
        )
        st.rerun()

# Every filter uses None for "don't narrow by this", so a pet called "all pets"
# or a block called "any block" can't be mistaken for the catch-all option.
with st.container(horizontal=True, vertical_alignment="bottom"):
    pet_filter = st.selectbox(
        "Pet",
        [None] + [p.name for p in owner.pets],
        format_func=lambda name: "all pets" if name is None else name,
        key="filter-pet",
    )
    priority_filter = st.selectbox(
        "Priority",
        [None] + PRIORITIES,
        format_func=lambda value: "any priority" if value is None else value,
        key="filter-priority",
    )
    block_filter = st.selectbox(
        "Time block",
        [None] + [b["label"] for b in blocks],
        format_func=lambda label: "any block" if label is None else label,
        key="filter-block",
    )
    status_filter = st.selectbox(
        "Status",
        [None, False, True],
        format_func=lambda done: {None: "any status", False: "to do", True: "done"}[done],
        key="filter-status",
    )
    # Plain strings rather than the None sentinel the other filters use:
    # these three options are fixed, so none of them can collide with a pet
    # name or block label someone typed.
    due_filter = st.selectbox(
        "Due",
        ["today & overdue", "upcoming", "all dates"],
        key="filter-due",
    )
    sort_choice = st.selectbox(
        "Sort",
        [None, "shortest first", "longest first"],
        format_func=lambda choice: "order added" if choice is None else choice,
        key="sort-tasks",
    )

# Filtering and sorting are backend decisions; this file only says which
# options were picked.
visible_tasks = owner.filter_tasks(
    pet_name=pet_filter,
    completed=status_filter,
    priority=priority_filter,
    preferred_block=block_filter,
    due_on_or_before=TODAY if due_filter == "today & overdue" else None,
    due_after=TODAY if due_filter == "upcoming" else None,
)
if sort_choice is not None:
    visible_tasks = Scheduler().sort_by_duration(
        visible_tasks, descending=sort_choice == "longest first"
    )

task_count = len(owner.get_all_tasks())
if not task_count:
    st.caption("No tasks yet.")
elif not visible_tasks:
    st.caption("No tasks match these filters.")
else:
    st.caption(f"Showing {len(visible_tasks)} of {task_count} task(s).")

for task in visible_tasks:
    # The list is flat now, so each row names the pet it belongs to and reaches
    # that pet through the task's own back-reference.
    pet = task.pet
    slot = f"{id(pet)}-{id(task)}"
    if st.session_state.editing_task == id(task):
        # A block this task prefers may have been renamed or removed since;
        # keep it in the list so editing something else doesn't silently drop
        # the preference.
        block_options = [None] + [b["label"] for b in blocks]
        current_block = task.preferred_block
        if current_block not in block_options:
            block_options.append(current_block)

        with st.container(border=True):
            with st.form(f"edit-task-{slot}", border=False):
                with st.container(horizontal=True, vertical_alignment="bottom"):
                    edited_title = st.text_input(
                        "Task", value=task.title, key=f"task-title-{slot}"
                    )
                    edited_duration = st.number_input(
                        "Duration (minutes)",
                        min_value=1,
                        max_value=240,
                        value=task.duration_minutes,
                        key=f"task-duration-{slot}",
                    )
                with st.container(horizontal=True, vertical_alignment="bottom"):
                    edited_priority = st.selectbox(
                        "Priority",
                        PRIORITIES,
                        index=PRIORITIES.index(task.priority),
                        key=f"task-priority-{slot}",
                    )
                    edited_block = st.selectbox(
                        "Preferred time",
                        block_options,
                        index=block_options.index(current_block),
                        format_func=preference_label,
                        key=f"task-block-{slot}",
                    )
                with st.container(horizontal=True, vertical_alignment="bottom"):
                    edited_frequency = st.selectbox(
                        "Repeats",
                        FREQUENCIES,
                        index=FREQUENCIES.index(task.frequency),
                        key=f"task-frequency-{slot}",
                    )
                    edited_due = st.date_input(
                        "Due", value=task.due_date, key=f"task-due-{slot}"
                    )
                    task_saved = st.form_submit_button("Save", icon=":material/check:")
                    task_cancelled = st.form_submit_button("Cancel", icon=":material/close:")

        if task_cancelled:
            st.session_state.editing_task = None
            st.rerun()
        if task_saved:
            # Same checks as creating a task, so an edit can't put the task
            # into a state the constructor would have rejected.
            try:
                task.update_details(
                    title=edited_title,
                    duration_minutes=int(edited_duration),
                    priority=edited_priority,
                    preferred_block=edited_block,
                    frequency=edited_frequency,
                    due_date=edited_due,
                )
            except ValueError as error:
                st.error(str(error), icon=":material/error:")
            else:
                st.session_state.editing_task = None
                st.rerun()
        continue

    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        label = f"~~{task.title}~~" if task.completed else task.title
        schedule = due_label(task)
        st.markdown(
            f"**{pet.name}** · {label} · {task.duration_minutes} min · {task.priority}"
            + (
                f" · prefers {task.preferred_block}"
                if task.preferred_block
                else " · no block preference"
            )
            + (f" · {schedule}" if schedule else "")
        )
        if task.completed:
            if st.button("Undo", key=f"undo-{slot}", icon=":material/undo:"):
                # Takes back the occurrence the completion queued, as long as
                # it hasn't been touched since.
                withdrawn = pet.uncomplete_task(task)
                if withdrawn is not None:
                    st.toast(
                        f"{withdrawn.title} on {withdrawn.due_date:%a %d %b} withdrawn.",
                        icon=":material/undo:",
                    )
                st.rerun()
        elif st.button("Mark done", key=f"done-{slot}", icon=":material/check:"):
            # The pet queues the next occurrence of a repeating task.
            follow_up = pet.complete_task(task)
            if follow_up is not None:
                st.toast(
                    f"Next {follow_up.frequency} {follow_up.title} "
                    f"queued for {follow_up.due_date:%a %d %b}.",
                    icon=":material/event_repeat:",
                )
            st.rerun()
        if st.button("Edit", key=f"edit-task-{slot}", icon=":material/edit:"):
            st.session_state.editing_task = id(task)
            st.session_state.editing_pet = None
            st.session_state.deleting_pet = None
            st.rerun()
        # Deleting one task is cheap to redo, so it goes through without a
        # confirmation step - unlike deleting a whole pet.
        if st.button("Remove", key=f"remove-task-{slot}", icon=":material/delete:"):
            pet.remove_task(task)
            st.rerun()

# --- Availability ------------------------------------------------------------
st.subheader("Availability")
st.caption("The windows of time you actually have today.")

for index, block in enumerate(blocks):
    block_id = block["id"]
    with st.container(horizontal=True, vertical_alignment="bottom"):
        block["label"] = st.text_input("Label", value=block["label"], key=f"label-{block_id}")
        block["start"] = st.time_input("Starts", value=block["start"], key=f"start-{block_id}")
        block["end"] = st.time_input("Ends", value=block["end"], key=f"end-{block_id}")
        if st.button("Remove", key=f"remove-{block_id}", icon=":material/delete:"):
            cleared = retarget_preferences(owner.get_all_tasks(), block["label"], None)
            blocks.pop(index)
            if cleared:
                st.toast(
                    f"{cleared} task(s) no longer prefer {block['label']!r}.",
                    icon=":material/info:",
                )
            st.rerun()

if st.button("Add a time block", icon=":material/add:"):
    # Labels have to be unique, so skip past any number already taken -
    # removing "block 2" and adding a block shouldn't mint a second "block 3".
    taken = {block["label"].strip().lower() for block in blocks}
    number = len(blocks) + 1
    while f"block {number}" in taken:
        number += 1
    blocks.append(
        {
            "id": next(st.session_state.block_ids),
            "label": f"block {number}",
            "start": time(12, 0),
            "end": time(13, 0),
        }
    )
    st.rerun()

# Build the TimeBlocks here rather than inside the Generate branch, so a block
# that ends before it starts or overlaps its neighbour is called out while the
# inputs are still on screen. Both checks live in the backend.
try:
    time_blocks = [
        TimeBlock(
            label=block["label"],
            start_time=block["start"].strftime("%H:%M"),
            end_time=block["end"].strftime("%H:%M"),
        )
        for block in blocks
    ]
    validate_time_blocks(time_blocks)
    availability_ok = True
except ValueError as error:
    st.error(str(error), icon=":material/error:")
    availability_ok = False

if availability_ok and time_blocks:
    total_available = sum(block.duration_minutes() for block in time_blocks)
    st.caption(f"{total_available} minutes available across {len(time_blocks)} block(s).")

# --- Today's plan ------------------------------------------------------------
st.subheader("Today's plan")


def plan_inputs() -> tuple:
    """What a plan depends on, so a stored one can be called out as stale.

    Completion is deliberately left out: ticking a task off is progress
    against the plan, not a reason to rebuild it.
    """
    return (
        tuple(
            (task.title, task.duration_minutes, task.priority, task.preferred_block)
            for task in owner.get_all_tasks()
        ),
        tuple((block.label, block.start_time, block.end_time) for block in time_blocks),
    )


all_tasks = owner.get_all_tasks()
# Today's work: due today or earlier, so an unfinished task from yesterday
# doesn't quietly fall out of the plan. Occurrences queued for later wait.
todo = owner.filter_tasks(completed=False, due_on_or_before=TODAY)

if not availability_ok:
    st.info("Fix the availability above to build a plan.", icon=":material/schedule:")
elif not time_blocks:
    st.info("Add a time block above to build a plan.", icon=":material/schedule:")
elif st.button("Generate schedule", type="primary", icon=":material/calendar_month:"):
    if not all_tasks:
        st.info("Add a task first - there's nothing to schedule yet.", icon=":material/list:")
    elif not todo:
        st.success("Everything is done for today.", icon=":material/celebration:")
    else:
        st.session_state.plan = Scheduler().build_plan(todo, time_blocks)
        st.session_state.plan_minutes = sum(b.duration_minutes() for b in time_blocks)
        st.session_state.plan_inputs = plan_inputs()
        st.rerun()

# Rendered outside the button so the plan stays on screen while tasks are
# ticked off; it used to vanish on the next interaction.
plan = st.session_state.plan
if plan is not None:
    if st.session_state.plan_inputs != plan_inputs():
        st.caption(
            ":material/history: Tasks or availability have changed since this plan was built."
        )

    scheduled_minutes = sum(entry.task.duration_minutes for entry in plan.scheduled_tasks)
    left, middle, right = st.columns(3)
    left.metric("Scheduled", len(plan.scheduled_tasks), border=True)
    middle.metric("Dropped", len(plan.dropped_tasks), border=True)
    right.metric(
        "Minutes used", f"{scheduled_minutes} / {st.session_state.plan_minutes}", border=True
    )

    if plan.scheduled_tasks:
        st.dataframe(
            [
                {
                    "Time": entry.start_time,
                    "Done": entry.task.completed,
                    "Task": entry.task.title,
                    "Pet": entry.task.pet.name if entry.task.pet else "unassigned",
                    "Minutes": entry.task.duration_minutes,
                    "Priority": entry.task.priority,
                    "Block": entry.block_label,
                }
                for entry in plan.scheduled_tasks
            ],
            hide_index=True,
            alt="Today's scheduled pet care tasks in clock order",
        )

    # Normally empty - the scheduler packs tasks one after another and blocks
    # can't overlap - but shown rather than assumed away.
    for warning in plan.conflicts:
        st.warning(warning, icon=":material/warning:")

    if plan.dropped_tasks:
        st.warning(
            "No block had enough time left for: "
            + ", ".join(
                f"{task.title} ({task.duration_minutes} min)" for task in plan.dropped_tasks
            ),
            icon=":material/schedule:",
        )

    with st.expander("Why this plan?"):
        st.text(plan.explain())
