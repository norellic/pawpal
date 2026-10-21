# PawPal+

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## ✨ Features

What the app does, in plain terms. The methods behind each one, and how they work, are under
[Smarter Scheduling](#-smarter-scheduling).

- **Priority-based daily planning.** Higher-priority tasks get time first, and shorter tasks go
  first within a priority. Anything that doesn't fit is left out and listed with the reason.
- **Availability as time blocks.** Enter windows like morning 07:00–09:00. Labels must be unique
  and blocks can't overlap, so the same minute is never counted twice.
- **Block preferences that bend.** A task can prefer a block. If that block is full it moves to
  the first block with room instead of being dropped, and the plan says it was moved. Renaming or
  removing a block updates the tasks that preferred it.
- **Sorting.** The plan comes back in clock order however the tasks were added, and the task list
  can be sorted shortest or longest first.
- **Filtering.** Narrow the task list by pet, status, priority, time block and due date, alone or
  combined.
- **Conflict warnings.** Two overlapping tasks, for the same pet or different pets, produce a
  warning instead of an error. Tasks that only touch aren't flagged.
- **Daily and weekly recurrence.** Completing a repeating task queues the next one, and Undo
  takes it back unless it has been edited since.
- **Due dates.** Today's plan includes tasks due today or earlier, so an unfinished task carries
  forward and one queued for tomorrow waits.
- **Explained plans.** Every placement, move and drop comes with a reason.
- **Full editing.** Pets and tasks can be added, edited and removed. Deleting a pet asks first
  because it takes its tasks with it. Names, titles, durations and priorities are validated the
  same way on creation and on edit.

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

An excerpt of `python main.py`: a household's tasks, the day's availability, and the plan built from them. The full run, including filtering, recurrence and conflict checks, is under the Demo Walkthrough.

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
# Run the full test suite, listing every test by name:
python -m pytest -v

# Run with coverage (needs: pip install pytest-cov):
python -m pytest --cov
```

The suite is in `test/`: `test_pawpal.py` covers the backend (sorting, filtering, recurrence,
conflict detection, the packing rules and input validation) and `test_app.py` drives the
Streamlit UI headlessly with `AppTest`. Test names are written as sentences describing the
behaviour they check, so the list below doubles as a summary of what is covered.

Sample test output:

```
============================= test session starts =============================
platform win32 -- Python 3.13.4, pytest-9.1.1, pluggy-1.7.0
collecting ... collected 54 items

test/test_app.py::test_the_app_starts_by_asking_for_a_pet PASSED         [  1%]
test/test_app.py::test_a_duplicate_pet_name_is_refused_with_a_message PASSED [  3%]
test/test_app.py::test_deleting_a_pet_asks_before_removing_it PASSED     [  5%]
test/test_app.py::test_marking_a_daily_task_done_queues_tomorrows_in_the_app PASSED [  7%]
test/test_app.py::test_undo_takes_back_the_queued_occurrence PASSED      [  9%]
test/test_app.py::test_the_plan_stays_on_screen_after_marking_a_task_done PASSED [ 11%]
test/test_app.py::test_generating_with_no_tasks_says_there_is_nothing_to_schedule PASSED [ 12%]
test/test_app.py::test_overlapping_availability_is_flagged_and_blocks_the_plan PASSED [ 14%]
test/test_app.py::test_renaming_a_block_carries_over_to_tasks_that_preferred_it PASSED [ 16%]
test/test_app.py::test_filters_and_sort_change_what_the_list_shows PASSED [ 18%]
test/test_pawpal.py::test_mark_complete_changes_task_status PASSED       [ 20%]
test/test_pawpal.py::test_add_task_increases_pet_task_count PASSED       [ 22%]
test/test_pawpal.py::test_blocks_must_have_unique_labels PASSED          [ 24%]
test/test_pawpal.py::test_a_block_needs_a_label PASSED                   [ 25%]
test/test_pawpal.py::test_next_occurrence_steps_the_due_date_by_frequency PASSED [ 27%]
test/test_pawpal.py::test_an_unknown_frequency_is_rejected PASSED        [ 29%]
test/test_pawpal.py::test_completing_a_repeating_task_queues_the_next_one PASSED [ 31%]
test/test_pawpal.py::test_completing_twice_does_not_queue_a_second_copy PASSED [ 33%]
test/test_pawpal.py::test_undo_withdraws_the_queued_occurrence PASSED    [ 35%]
test/test_pawpal.py::test_undo_keeps_a_queued_occurrence_that_has_been_touched PASSED [ 37%]
test/test_pawpal.py::test_filter_tasks_splits_today_from_what_is_queued PASSED [ 38%]
test/test_pawpal.py::test_find_conflicts_warns_instead_of_raising PASSED [ 40%]
test/test_pawpal.py::test_back_to_back_tasks_are_not_a_conflict PASSED   [ 42%]
test/test_pawpal.py::test_build_plan_produces_a_plan_with_no_conflicts PASSED [ 44%]
test/test_pawpal.py::test_sort_by_time_puts_scheduled_tasks_in_clock_order PASSED [ 46%]
test/test_pawpal.py::test_sort_by_time_is_not_fooled_by_afternoon_times PASSED [ 48%]
test/test_pawpal.py::test_sort_by_duration_runs_both_ways PASSED         [ 50%]
test/test_pawpal.py::test_filter_tasks_narrows_by_pet_status_priority_and_block PASSED [ 51%]
test/test_pawpal.py::test_overlapping_blocks_are_rejected_but_touching_ones_are_fine PASSED [ 53%]
test/test_pawpal.py::test_build_plan_refuses_to_schedule_against_overlapping_blocks PASSED [ 55%]
test/test_pawpal.py::test_update_details_edits_a_task_but_rejects_bad_details PASSED [ 57%]
test/test_pawpal.py::test_update_details_leaves_completion_and_pet_alone PASSED [ 59%]
test/test_pawpal.py::test_remove_task_drops_only_that_task PASSED        [ 61%]
test/test_pawpal.py::test_update_details_renames_a_pet_but_rejects_a_blank_name PASSED [ 62%]
test/test_pawpal.py::test_remove_pet_drops_only_that_pet_and_its_tasks PASSED [ 64%]
test/test_pawpal.py::test_pet_names_must_be_unique_within_a_household PASSED [ 66%]
test/test_pawpal.py::test_owner_and_pet_names_cannot_be_blank PASSED     [ 68%]
test/test_pawpal.py::test_retarget_preferences_follows_a_renamed_or_removed_block PASSED [ 70%]
test/test_pawpal.py::test_two_tasks_at_exactly_the_same_time_are_flagged PASSED [ 72%]
test/test_pawpal.py::test_plan_explanation_reports_conflicts_only_when_there_are_some PASSED [ 74%]
test/test_pawpal.py::test_completing_a_weekly_task_queues_one_for_the_following_week PASSED [ 75%]
test/test_pawpal.py::test_a_repeating_task_keeps_repeating PASSED        [ 77%]
test/test_pawpal.py::test_recurrence_crosses_month_and_year_boundaries PASSED [ 79%]
test/test_pawpal.py::test_a_task_moves_to_another_block_when_its_preferred_one_is_full PASSED [ 81%]
test/test_pawpal.py::test_a_task_too_big_for_every_block_is_dropped_with_a_reason PASSED [ 83%]
test/test_pawpal.py::test_an_empty_block_list_drops_everything_without_crashing PASSED [ 85%]
test/test_pawpal.py::test_an_empty_task_list_makes_an_empty_plan PASSED  [ 87%]
test/test_pawpal.py::test_tasks_that_exactly_fill_a_block_fit_and_one_more_minute_does_not PASSED [ 88%]
test/test_pawpal.py::test_higher_priority_is_placed_first_and_shorter_breaks_ties PASSED [ 90%]
test/test_pawpal.py::test_priority_beats_fitting_more_tasks_in PASSED    [ 92%]
test/test_pawpal.py::test_a_task_cannot_be_created_with_bad_details PASSED [ 94%]
test/test_pawpal.py::test_a_time_block_must_be_a_real_window PASSED      [ 96%]
test/test_pawpal.py::test_all_tasks_come_back_in_the_order_they_were_added_across_pets PASSED [ 98%]
test/test_pawpal.py::test_a_pet_can_be_renamed_to_a_different_case_of_its_own_name PASSED [100%]

============================= 54 passed in 4.40s ==============================
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

PawPal+ runs in the browser with `streamlit run app.py`, and the same logic can be exercised
in the terminal with `python main.py`.

### What's on the page

The page reads top to bottom as four sections.

1. **Household.** Edit the owner name, add a pet (name and free-text species), and see each pet
   as a row with its task count. Each pet has **Edit** and **Delete** buttons; deleting asks for
   confirmation first because the pet's tasks go with it. Pet names must be unique and the owner
   name can't be blank.
2. **Tasks.** An **Add a task** form takes the pet, title, duration, priority, preferred time
   block and how often it repeats (once, daily or weekly). Below it, a filter bar narrows the
   list by pet, priority, time block, status and due date, and a sort control orders it by
   duration. The list is flat, in the order tasks were added, with the pet named on every row.
   Each row has **Mark done** (or **Undo**), **Edit** and **Remove**.
3. **Availability.** The day's time blocks, each with a label and start and end times. A running
   total shows the minutes available. Overlapping blocks or duplicate labels show an error and
   hide the Generate button until fixed.
4. **Today's plan.** **Generate schedule** builds the plan and shows how many tasks were
   scheduled and dropped, the minutes used out of the minutes available, a table in clock order,
   any conflict or dropped-task warnings, and a "Why this plan?" explanation.

### An example workflow

1. **Add two pets.** Enter *Mochi* (dog) and *Biscuit* (cat) in the Add a pet form. The form
   clears after each one.
2. **Add tasks.** For Mochi add *Morning walk* (30 min, high, prefers morning, repeats daily),
   *Evening walk* (25 min, medium, prefers evening) and *Brushing* (15 min, low). For Biscuit add
   *Feed Biscuit* (5 min, high, prefers morning). The task form keeps its values after each add, so
   adding the same task for different times of day is quick.
3. **Check the availability.** The two default blocks, morning 07:00–09:00 and evening
   17:30–19:00, give 210 minutes.
4. **Try the filters.** Pick *Mochi* in the Pet filter to see only Mochi's tasks, or sort by
   *longest first*. Setting Priority to *high* shows the walk and Biscuit's feeding.
5. **Generate the schedule.** The plan comes back in clock order: *Feed Biscuit* at 07:00,
   *Morning walk* at 07:05, *Brushing* at 07:35 and *Evening walk* at 17:30, using 75 of 210
   minutes. Open "Why this plan?" to see the reason for each placement.
6. **Mark the daily walk done.** A message says the next one is queued for tomorrow. Today's
   walk stays in the list, struck through, and tomorrow's copy appears under the Due filter's
   *upcoming* option. The plan stays on screen, with a note that tasks have changed since it was
   built.
7. **Undo.** Click Undo on the walk and tomorrow's queued copy is withdrawn.
8. **Break the availability.** Add a time block that overlaps the morning one. An error names the
   two blocks and the Generate button is replaced until it's fixed.

### Key scheduler behaviors

These are listed under [Features](#-features), and the output below shows each of them running.
Look for these headings:

- **Today's Tasks** shows tasks listed in the order they were added, deliberately out of clock order.
- **Filtering** and **Sorting by duration** show the filters and both sort directions.
- **Recurrence** shows daily and weekly tasks queuing their next occurrence, a one-off queuing
  nothing, and Undo taking a queued task back.
- **Today's Schedule** shows the plan in clock order, with the reason for each placement.
- **Conflict detection** shows warnings for overlapping tasks, and none for tasks that only touch.

### Sample CLI output

This is the output of `python main.py`. The dates are relative to the day it was run.

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

Filtering
========================================================================
Mochi's tasks only:
  - Evening walk    25 min  [medium] Mochi    to do once   due Wed 21 Oct  prefers: evening
  - Morning walk    30 min  [high  ] Mochi    to do daily  due Wed 21 Oct  prefers: morning
  - Brushing        15 min  [low   ] Mochi    to do weekly due Wed 21 Oct  prefers: any
  - Breakfast       10 min  [high  ] Mochi    to do once   due Wed 21 Oct  prefers: morning

Still to do:
  - Evening walk    25 min  [medium] Mochi    to do once   due Wed 21 Oct  prefers: evening
  - Morning walk    30 min  [high  ] Mochi    to do daily  due Wed 21 Oct  prefers: morning
  - Brushing        15 min  [low   ] Mochi    to do weekly due Wed 21 Oct  prefers: any
  - Breakfast       10 min  [high  ] Mochi    to do once   due Wed 21 Oct  prefers: morning
  - Puzzle toy      20 min  [low   ] Biscuit  to do once   due Wed 21 Oct  prefers: evening
  - Litter box      10 min  [medium] Biscuit  to do once   due Wed 21 Oct  prefers: any

Already done:
  - Feed Biscuit     5 min  [high  ] Biscuit  done  daily  due Wed 21 Oct  prefers: morning

Biscuit's high-priority tasks (filters combine):
  - Feed Biscuit     5 min  [high  ] Biscuit  done  daily  due Wed 21 Oct  prefers: morning

Anything wanting the morning block:
  - Morning walk    30 min  [high  ] Mochi    to do daily  due Wed 21 Oct  prefers: morning
  - Breakfast       10 min  [high  ] Mochi    to do once   due Wed 21 Oct  prefers: morning
  - Feed Biscuit     5 min  [high  ] Biscuit  done  daily  due Wed 21 Oct  prefers: morning

Sorting by duration
========================================================================
Shortest first:
  - Feed Biscuit     5 min  [high  ] Biscuit  done  daily  due Wed 21 Oct  prefers: morning
  - Breakfast       10 min  [high  ] Mochi    to do once   due Wed 21 Oct  prefers: morning
  - Litter box      10 min  [medium] Biscuit  to do once   due Wed 21 Oct  prefers: any
  - Brushing        15 min  [low   ] Mochi    to do weekly due Wed 21 Oct  prefers: any
  - Puzzle toy      20 min  [low   ] Biscuit  to do once   due Wed 21 Oct  prefers: evening
  - Evening walk    25 min  [medium] Mochi    to do once   due Wed 21 Oct  prefers: evening
  - Morning walk    30 min  [high  ] Mochi    to do daily  due Wed 21 Oct  prefers: morning

Longest first:
  - Morning walk    30 min  [high  ] Mochi    to do daily  due Wed 21 Oct  prefers: morning
  - Evening walk    25 min  [medium] Mochi    to do once   due Wed 21 Oct  prefers: evening
  - Puzzle toy      20 min  [low   ] Biscuit  to do once   due Wed 21 Oct  prefers: evening
  - Brushing        15 min  [low   ] Mochi    to do weekly due Wed 21 Oct  prefers: any
  - Breakfast       10 min  [high  ] Mochi    to do once   due Wed 21 Oct  prefers: morning
  - Litter box      10 min  [medium] Biscuit  to do once   due Wed 21 Oct  prefers: any
  - Feed Biscuit     5 min  [high  ] Biscuit  done  daily  due Wed 21 Oct  prefers: morning

Recurrence
========================================================================
  Morning walk   daily  -> next one due Thu 22 Oct (1 day(s) later)
  Brushing       weekly -> next one due Wed 28 Oct (7 day(s) later)
  Breakfast      once   -> nothing queued, it was a one-off

  Completing the same task twice doesn't queue a second copy:
    Mochi had 6 tasks, still has 6

  Undo takes the queued occurrence back:
    withdrew Morning walk due Thu 22 Oct
    Mochi now has 5 tasks, walk completed=False

  Queued for later (not part of today's plan):
  - Brushing        15 min  [low   ] Mochi    to do weekly due Wed 28 Oct  prefers: any

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

Conflict detection
========================================================================

  same pet, overlapping: 1 warning(s)
    ! Mochi is booked twice: 'Morning walk' (Mochi) 07:00-07:30 overlaps 'Brushing' (Mochi) 07:15-07:30

  two pets, overlapping: 3 warning(s)
    ! Mochi is booked twice: 'Morning walk' (Mochi) 07:00-07:30 overlaps 'Brushing' (Mochi) 07:15-07:30
    ! Two tasks want the same minutes: 'Morning walk' (Mochi) 07:00-07:30 overlaps 'Feed Biscuit' (Biscuit) 07:20-07:30
    ! Two tasks want the same minutes: 'Brushing' (Mochi) 07:15-07:30 overlaps 'Feed Biscuit' (Biscuit) 07:20-07:30

  back to back: 0 warning(s)
```
