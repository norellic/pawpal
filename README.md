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
| `Owner` | Holds the household's pets. `get_all_tasks()` flattens every pet's tasks into one list. |
| `Pet` | Holds its own tasks. `add_task()` attaches a task and sets its back-reference. |
| `Task` | A record of what needs doing: title, duration, priority, optional preferred block, completion status. |
| `TimeBlock` | One window of owner availability, e.g. morning 07:00–09:00. |
| `Scheduler` | Decides what gets scheduled, where, and in what order. |
| `Plan` | The result: scheduled tasks, dropped tasks, and `explain()`. |
| `ScheduledTask` | One task paired with the block and start time it landed in. |

**How they work together.** `Owner.get_all_tasks()` collects tasks from every pet into a flat
list. The caller filters out completed tasks and passes that list, plus the day's `TimeBlock`s,
to `Scheduler.build_plan()`. The scheduler sorts by priority — ties broken by shorter duration
first — then places each task into its preferred block if that block still has room, falling
back to any block with room, since `preferred_block` is a preference rather than a hard
constraint. Tasks that fit nowhere are dropped rather than overflowing a block. The returned
`Plan` holds `ScheduledTask`s in clock order alongside whatever was dropped, and
`Plan.explain()` turns that into a readable justification for every placement.

`Scheduler` never receives an `Owner`, only a flat list of tasks. That keeps the scheduling
logic independent of how tasks are stored — which is why adding support for multiple pets
later required no change to the scheduler at all.

**Scope:** one day, no recurring tasks. See `reflection.md` for the reasoning behind these
tradeoffs and how the design changed along the way.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
Today's Tasks for Jordan Rivera
====================================================

Mochi (dog)
  - Morning walk    30 min  [high  ] prefers: morning
  - Breakfast       10 min  [high  ] prefers: morning
  - Evening walk    25 min  [medium] prefers: evening
  - Brushing        15 min  [low   ] prefers: any

Biscuit (cat)
  - Feed Biscuit     5 min  [high  ] prefers: morning
  - Litter box      10 min  [medium] prefers: any
  - Puzzle toy      20 min  [low   ] prefers: evening

7 tasks, 115 minutes of care needed today.

Availability
====================================================
  morning  07:00 - 09:00
  evening  17:30 - 19:00

Today's Schedule (210 minutes available)
====================================================
Scheduled 7 of 7 tasks.

  07:00  Feed Biscuit (Biscuit) - high priority, preferred block 'morning' had room
  07:05  Breakfast (Mochi) - high priority, preferred block 'morning' had room
  07:15  Morning walk (Mochi) - high priority, preferred block 'morning' had room
  07:45  Litter box (Biscuit) - medium priority, no block preference, placed in morning
  07:55  Brushing (Mochi) - low priority, no block preference, placed in morning
  17:30  Evening walk (Mochi) - medium priority, preferred block 'evening' had room
  17:55  Puzzle toy (Biscuit) - low priority, preferred block 'evening' had room
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

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | | e.g., by priority, duration |
| Filtering | | e.g., skip tasks if time runs out |
| Conflict handling | | e.g., overlapping time slots |
| Recurring tasks | | e.g., daily vs. weekly |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
