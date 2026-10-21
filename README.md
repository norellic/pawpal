# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🧩 Implementation Summary

The backend lives in `pawpal_system.py` and was built CLI-first: `main.py` builds a sample
household and prints a plan to the terminal, so the logic could be verified before any UI work.

| Class | Responsibility |
|-------|----------------|
| `Owner` | Holds the household's pets and the rules that span them: names must be unique and the owner's own name can't be blank. `add_pet()`, `update_pet()` and `remove_pet()` manage the household; `get_all_tasks()` flattens every pet's tasks into one list in the order they were added; `filter_tasks()` narrows that list. |
| `Pet` | Holds its own tasks. `add_task()` attaches a task and sets its back-reference, `remove_task()` and `update_details()` manage them, and `complete_task()` / `uncomplete_task()` mark a task done or undone while queuing or withdrawing its next occurrence. |
| `Task` | A record of what needs doing: title, duration, priority, optional preferred block, completion status, how often it repeats (`frequency`) and the day it is due (`due_date`). `update_details()` re-applies the same checks as construction, and `next_occurrence()` builds the following copy of a repeating task. |
| `TimeBlock` | One window of owner availability, e.g. morning 07:00–09:00. Needs a label and must end after it starts. |
| `Scheduler` | Decides what gets scheduled, where, and in what order: `build_plan()` places tasks, `sort_by_time()` and `sort_by_duration()` order them, and `find_conflicts()` checks the result for overlaps. |
| `Plan` | The result: scheduled tasks, dropped tasks, any conflict warnings, and `explain()`. |
| `ScheduledTask` | One task paired with the block and start time it landed in. |

Two rules apply to a *set* of objects rather than to any one of them, so they are module-level
functions instead of methods: `validate_time_blocks()` (block labels must be unique and blocks
must not overlap) and `retarget_preferences()` (renaming or removing a block updates the tasks
that preferred it). `build_plan()` calls the first itself, so no caller can skip it.

**How they work together.** The caller asks `Owner.filter_tasks()` for the tasks that belong in
today's plan: not completed, and due today or earlier, so an unfinished task from yesterday
carries forward while one queued for tomorrow waits. That flat list, plus the day's `TimeBlock`s,
goes to `Scheduler.build_plan()`. The scheduler sorts by priority — ties broken by shorter
duration first — then places each task into its preferred block if that block still has room,
falling back to any block with room, since `preferred_block` is a preference rather than a hard
constraint. Tasks that fit nowhere are dropped rather than overflowing a block. The returned
`Plan` holds `ScheduledTask`s in clock order alongside whatever was dropped and any conflict
warnings, and `Plan.explain()` turns that into a readable justification for every placement.

`Scheduler` never receives an `Owner`, only a flat list of tasks. That keeps the scheduling
logic independent of how tasks are stored — which is why adding support for multiple pets
later required no change to the scheduler at all.

**Scope:** one day's plan, built from tasks due today or earlier. Tasks can repeat daily or
weekly (see Smarter Scheduling below). See `reflection.md` for the reasoning behind these
tradeoffs and how the design changed along the way.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
Today's Tasks for Jordan Rivera
========================================================================
  - Evening walk    25 min  [medium] Mochi    to do once   due Wed 21 Oct  prefers: evening
  - Morning walk    30 min  [high  ] Mochi    to do daily  due Wed 21 Oct  prefers: morning
  - Brushing        15 min  [low   ] Mochi    to do weekly due Wed 21 Oct  prefers: any
  - Breakfast       10 min  [high  ] Mochi    to do once   due Wed 21 Oct  prefers: morning
  - Puzzle toy      20 min  [low   ] Biscuit  to do once   due Wed 21 Oct  prefers: evening
  - Feed Biscuit     5 min  [high  ] Biscuit  done  daily  due Wed 21 Oct  prefers: morning
  - Litter box      10 min  [medium] Biscuit  to do once   due Wed 21 Oct  prefers: any

7 tasks, 115 minutes of care needed today.

Availability
========================================================================
  morning  07:00 - 09:00
  evening  17:30 - 19:00

Today's Schedule (210 minutes available)
========================================================================
  07:00  Morning walk   (morning)
  07:30  Litter box     (morning)
  17:30  Evening walk   (evening)
  17:55  Puzzle toy     (evening)

Scheduled 4 of 4 tasks.

  07:00  Morning walk (Mochi) - high priority, preferred block 'morning' had room
  07:30  Litter box (Biscuit) - medium priority, no block preference, placed in morning
  17:30  Evening walk (Mochi) - medium priority, preferred block 'evening' had room
  17:55  Puzzle toy (Biscuit) - low priority, preferred block 'evening' had room

  conflicts found in this plan: 0
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
python -m pytest

# Run with coverage:
python -m pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

| Feature | Method(s) | What it does |
|---------|-----------|--------------|
| Sorting by time | `Scheduler.sort_by_time()` | Puts scheduled tasks in clock order, earliest first |
| Sorting by duration | `Scheduler.sort_by_duration()` | Shortest or longest first, for the task list |
| Filtering | `Owner.filter_tasks()` | Narrows tasks by pet, status, priority, time block and due date |
| Conflict detection | `Scheduler.find_conflicts()` | Returns a warning for any two tasks whose times overlap |
| Recurring tasks | `Task.next_occurrence()`, `Pet.complete_task()`, `Pet.uncomplete_task()` | Completing a daily or weekly task queues the next one |

### Sorting

`Scheduler.sort_by_time()` orders `ScheduledTask`s by start time using `sorted()` with a lambda
key. Start times are zero-padded `"HH:MM"` strings, so plain text comparison gives the same
order as the clock (`"07:05"` before `"17:30"`) and nothing needs parsing. The padding is what
makes this safe: an unpadded `"7:05"` would sort *after* `"17:30"`. The sort is stable and
returns a new list. `build_plan()` runs its result through this, so tasks come back
earliest-first however they were added.

`Scheduler.sort_by_duration(tasks, descending=False)` is the same idea keyed on
`duration_minutes`. The app uses it for the Sort dropdown (order added / shortest first /
longest first).

### Filtering

`Owner.filter_tasks()` takes any combination of `pet_name`, `completed`, `priority`,
`preferred_block`, `due_on_or_before` and `due_after`. Every filter is optional, `None` means
"don't narrow by this", and filters combine with AND, so calling it with no arguments is the
same as `get_all_tasks()`. Pet names and block labels match ignoring case.

```python
owner.filter_tasks(pet_name="Mochi")                       # one pet's tasks
owner.filter_tasks(completed=False)                        # still to do
owner.filter_tasks(pet_name="Biscuit", priority="high")    # filters combine
owner.filter_tasks(due_on_or_before=today, completed=False)  # today's work
```

The task list in the app is a flat list in the order tasks were added, with a filter bar for
pet, priority, time block, status and due date, plus the sort dropdown above.

### Conflict detection

`Scheduler.find_conflicts()` is a lightweight check that returns **warning messages instead of
raising**. It sorts the entries by start time and compares each one's span (start plus
duration) with the entries that follow, stopping early once a later entry starts after the
current one ends. It checks real overlap, not just identical start times, and reports every
overlapping pair:

```
Mochi is booked twice: 'Morning walk' (Mochi) 07:00-07:30 overlaps 'Brushing' (Mochi) 07:15-07:30
Two tasks want the same minutes: 'Morning walk' (Mochi) 07:00-07:30 overlaps 'Feed Biscuit' (Biscuit) 07:20-07:30
```

Tasks that only touch (one ends at 07:30, the next starts at 07:30) are not a conflict, and
two different pets still clash because one owner can't do both at once. The result is stored
on `Plan.conflicts` and shown under the plan in the app.

Be aware that this is a safety net rather than a fix for a known bug. `build_plan()` packs tasks
one after another inside a block, and `validate_time_blocks()` rejects overlapping or
duplicate-labelled blocks, so a plan it builds never contains a conflict. `main.py` therefore
builds overlapping entries by hand to show the detector firing.

### Recurring tasks

A `Task` is one occurrence on one day. It carries a `frequency` (`"once"`, `"daily"` or
`"weekly"`) and a `due_date`, and `Task.next_occurrence()` returns a fresh, incomplete copy
dated one day or seven days later, or `None` for a one-off.

`Pet.complete_task()` marks a task done and adds that next occurrence to the pet's list.
`Task` decides what comes next and `Pet` decides where it goes, which keeps
`Task.mark_complete()` a plain status flip. Completing the same task twice doesn't queue a
second copy, and `Pet.uncomplete_task()` (the app's Undo button) takes the queued occurrence
back, but only while it is still untouched. If it has since been edited or completed it belongs
to the user and stays.

Today's plan is built from tasks due **today or earlier**, so an unfinished task from yesterday
carries forward while one queued for tomorrow waits. In the app, the Due filter switches
between *today & overdue*, *upcoming* and *all dates*. Running `python main.py` shows the dates
directly, since "tomorrow" never arrives while the app is open:

```
Morning walk   daily  -> next one due Thu 22 Oct (1 day(s) later)
Brushing       weekly -> next one due Wed 28 Oct (7 day(s) later)
Breakfast      once   -> nothing queued, it was a one-off
```

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
