"""PawPal+ Streamlit UI.

A thin bridge over pawpal_system.py: this file collects input and renders
output, but every scheduling decision is made by the backend classes.
"""

from datetime import time
from itertools import count

import streamlit as st

from pawpal_system import (
    PRIORITY_ORDER,
    Owner,
    Pet,
    Scheduler,
    Task,
    TimeBlock,
    validate_time_blocks,
)

st.set_page_config(page_title="PawPal+", page_icon=":material/pets:", layout="centered")

# Pull the valid priorities from the backend so the UI can't offer a value
# Task.__post_init__ would reject.
PRIORITIES = list(PRIORITY_ORDER)


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
    if f"label-{block['id']}" in st.session_state:
        block["label"] = st.session_state[f"label-{block['id']}"]
        block["start"] = st.session_state[f"start-{block['id']}"]
        block["end"] = st.session_state[f"end-{block['id']}"]

st.title("PawPal+")
st.caption("Plan the day's pet care around the time you actually have.")

# --- Household ---------------------------------------------------------------
st.subheader("Household")
owner.name = st.text_input("Owner name", value=owner.name)

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
        owner.add_pet(
            Pet(name=new_pet_name.strip(), species=new_species.strip() or "pet")
        )

if not owner.pets:
    st.info("Add a pet to get started.", icon=":material/pets:")
    st.stop()

st.caption(f"{owner.name} has {len(owner.pets)} pet(s): " + ", ".join(p.name for p in owner.pets))

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
            )
        )
        st.rerun()

for pet in owner.pets:
    # Widget keys are built from the object's identity rather than its position
    # or name, so renaming or removing a pet doesn't hand its stored widget
    # state to a neighbour, and two pets called "Mochi" stay distinct.
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
                # The backend rejects a blank name, so surface that rather
                # than letting an unnamed pet into the household.
                try:
                    pet.update_details(edited_name, edited_species)
                except ValueError as error:
                    st.error(str(error), icon=":material/error:")
                else:
                    st.session_state.editing_pet = None
                    st.rerun()
        else:
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{pet.name}** · {pet.species}")
                if st.button("Edit", key=f"edit-pet-{pet_key}", icon=":material/edit:"):
                    st.session_state.editing_pet = pet_key
                    st.session_state.deleting_pet = None
                    st.rerun()
                if st.button("Delete", key=f"delete-pet-{pet_key}", icon=":material/delete:"):
                    st.session_state.deleting_pet = pet_key
                    st.session_state.editing_pet = None
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

        if not pet.tasks:
            st.caption("No tasks yet.")
            continue
        for task in pet.tasks:
            slot = f"{pet_key}-{id(task)}"
            if st.session_state.editing_task == id(task):
                # A block this task prefers may have been renamed or removed
                # since; keep it in the list so editing something else doesn't
                # silently drop the preference.
                block_options = [None] + [b["label"] for b in blocks]
                current_block = task.preferred_block
                if current_block not in block_options:
                    block_options.append(current_block)

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
                        task_saved = st.form_submit_button("Save", icon=":material/check:")
                        task_cancelled = st.form_submit_button(
                            "Cancel", icon=":material/close:"
                        )

                if task_cancelled:
                    st.session_state.editing_task = None
                    st.rerun()
                if task_saved:
                    # Same checks as creating a task, so an edit can't put the
                    # task into a state the constructor would have rejected.
                    try:
                        task.update_details(
                            title=edited_title,
                            duration_minutes=int(edited_duration),
                            priority=edited_priority,
                            preferred_block=edited_block,
                        )
                    except ValueError as error:
                        st.error(str(error), icon=":material/error:")
                    else:
                        st.session_state.editing_task = None
                        st.rerun()
                continue

            with st.container(horizontal=True, vertical_alignment="center"):
                label = f"~~{task.title}~~" if task.completed else task.title
                st.markdown(
                    f"{label} · {task.duration_minutes} min · {task.priority}"
                    + (
                        f" · prefers {task.preferred_block}"
                        if task.preferred_block
                        else " · no block preference"
                    )
                )
                if task.completed:
                    if st.button("Undo", key=f"undo-{slot}", icon=":material/undo:"):
                        task.completed = False
                        st.rerun()
                elif st.button("Mark done", key=f"done-{slot}", icon=":material/check:"):
                    task.mark_complete()
                    st.rerun()
                if st.button("Edit", key=f"edit-task-{slot}", icon=":material/edit:"):
                    st.session_state.editing_task = id(task)
                    st.session_state.editing_pet = None
                    st.session_state.deleting_pet = None
                    st.rerun()
                # Deleting one task is cheap to redo, so it goes through
                # without a confirmation step — unlike deleting a whole pet.
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
            blocks.pop(index)
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

if not availability_ok:
    st.info("Fix the availability above to build a plan.", icon=":material/schedule:")
elif not time_blocks:
    st.info("Add a time block above to build a plan.", icon=":material/schedule:")
elif st.button("Generate schedule", type="primary", icon=":material/calendar_month:"):
    # Completed tasks are filtered here rather than inside get_all_tasks(), so
    # the lists above can still show everything.
    todo = [task for task in owner.get_all_tasks() if not task.completed]

    if not todo:
        st.success("Everything is done for today.", icon=":material/celebration:")
        st.stop()

    plan = Scheduler().build_plan(todo, time_blocks)

    available = sum(block.duration_minutes() for block in time_blocks)
    scheduled_minutes = sum(entry.task.duration_minutes for entry in plan.scheduled_tasks)
    left, middle, right = st.columns(3)
    left.metric("Scheduled", len(plan.scheduled_tasks), border=True)
    middle.metric("Dropped", len(plan.dropped_tasks), border=True)
    right.metric("Minutes used", f"{scheduled_minutes} / {available}", border=True)

    if plan.scheduled_tasks:
        st.dataframe(
            [
                {
                    "Time": entry.start_time,
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

    if plan.dropped_tasks:
        st.warning(
            "No block had enough time left for: "
            + ", ".join(f"{t.title} ({t.duration_minutes} min)" for t in plan.dropped_tasks),
            icon=":material/schedule:",
        )

    with st.expander("Why this plan?"):
        st.text(plan.explain())
