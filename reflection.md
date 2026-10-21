# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

Three core actions:
1. Owner should be able to add care tasks, each with a priority and duration
2. Owner should be able to indicate preferences and availability
3. Owner should be able to see why the plan chose what it chose

- Briefly describe your initial UML design. What classes did you include, and what responsibilities did you assign to each?

My first draft was a hierarchy of Owner, Pet, and Task. Owner held a name and a free-text preferences field, plus a method to add pets. Pet held name, species, breed, and age, plus a method to add tasks. Task was pure data — title, duration, priority, and a pair of fields for whether it repeated and how often.

On the scheduling side, a Scheduler took the list of tasks and a single `available_minutes` number representing how much time the owner had, sorted the tasks by priority, and packed them into that time budget. It returned a Plan, which held the tasks that fit (each paired with a start time, as a ScheduledTask) and the tasks that didn't, plus an `explain()` method to justify the choices. The Plan covered one day.

Responsibilities split roughly into three groups: Owner and Pet own the data and the relationships between them, Task is a passive record of what needs doing, and Scheduler holds all the decision-making — nothing else in the system decides what gets scheduled or when.

**b. Design changes**

- Did your design change during implementation? If yes, describe at least one change and why you made it.

Quite a bit. Most of the change happened while iterating on the UML itself, before writing any logic.

**Ownership and scope.** My first draft gave Owner a list of pets. I narrowed that to a single pet to keep the MVP small, then went back to multiple pets once it was clear the scheduler should plan for a household, not one animal. That round trip added a new responsibility to Owner: `get_all_tasks()`, which flattens every pet's task list into one collection. The question that settled it was who should know how tasks are nested — I decided the Scheduler shouldn't, so Owner absorbs the aggregation and hands over a flat list.

**Pruning attributes that did nothing.** The first draft carried fields that looked reasonable but had no consumer: `breed` and `age` on Pet, and a free-text `preferences` field on Owner. Preferences was the clearest case — nothing in the scheduling logic actually read it, and it wasn't stored in a usable format. I cut it because the intent behind it (when the owner wants things to happen) is already expressed through time blocks and priority.

**Recurrence.** My initial Task had `is_recurring` and `recurrence` fields, but since the plan only covers a single day, those fields had nothing to attach to — there was no concept of "tomorrow" for a weekly task to land on. I removed them rather than carry dead structure, and initially scoped the project to one day. That scoping didn't last: recurrence became a required feature later, and it came back in a different shape (see the update under "Deliberately deferred").

**Availability: one number became several blocks.** The Scheduler originally held a single `available_minutes` integer. That doesn't match how people actually have time — most owners have a morning window and an evening window, not one continuous span. I added a TimeBlock class (label, start, end) and changed `build_plan()` to take a list of them. That change cascaded: Task gained a `preferred_block` field, and ScheduledTask gained `block_label` so the plan can report where each task landed. I decided `preferred_block` is a soft preference, not a hard constraint — if the preferred block is full, the task still gets placed elsewhere rather than dropped.

**Completion.** Adding the ability to mark tasks done introduced a `completed` flag on Task, which raised a question I had to answer deliberately: should `get_all_tasks()` hide completed tasks? I decided no. A task history or mark-complete view would want the full list, and only the scheduler wants them excluded, so the filtering belongs at the call site rather than baked into data access. The deciding factor was which mistake is cheaper to undo — duplicating one filter line is easier to fix than unwinding a hidden filter that every future caller inherits.

**A gap I caught late.** Once an Owner could have multiple pets and tasks were flattened into a single list, nothing in the plan recorded which pet a task belonged to, so the output couldn't tell one dog's walk from another's. I added a `pet` back-reference on Task, set when `add_task()` is called.

**Deliberately deferred.** Priority ties currently break by shorter duration, which I flagged in the diagram as a rule to revisit. Recurrence was out of scope at this point, and I thought I had kept the seam where it would go: whatever decides which tasks are due today would live inside `get_all_tasks()`, so adding recurrence later shouldn't require changing Scheduler, Plan, or Task.

*Update: recurrence is in scope now, and that prediction was only half right.* Tasks can repeat daily or weekly, and completing one queues the next occurrence. The Scheduler really didn't need to change for it, which supports the through-line below. But Task did, contrary to what I wrote above: it gained a `frequency`, a `due_date`, and a `next_occurrence()` method, because a task had to become one occurrence on one day for "the next one" to mean anything. The seam also ended up in a different place than I guessed. Deciding what is due today is a `filter_tasks()` date filter on Owner rather than a change to `get_all_tasks()`, which still returns everything. Pet owns the logic that queues the next occurrence (`complete_task()`) and takes it back on Undo (`uncomplete_task()`), so that `Task.mark_complete()` stays the plain status flip it always was.

**The through-line.** Most of these changes came from asking the same question repeatedly: does this class actually need to know that detail, or can it just be handed a value? Keeping the Scheduler ignorant of Owner is why adding multi-pet support later cost almost nothing — I only had to change how the task list was assembled, not how it was scheduled.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

The scheduler weighs five things, and they are not equally strict.

1. **Time is the one hard constraint.** A task is only placed in a block that still has room for its full duration, and a task that fits nowhere is dropped with a stated reason rather than squeezed in. Blocks themselves have rules about them: labels must be unique and blocks can't overlap, because otherwise the same minute would be counted twice and the "minutes available" total would be a lie.
2. **Priority decides who gets scarce time.** Tasks are placed high to low, and within a priority shorter tasks go first. That tie-break is still a placeholder I flagged in the diagram; it mostly keeps the output deterministic.
3. **Block preference is soft.** If a task's preferred block is full it moves to the first block with room instead of being dropped, and the plan's explanation says it was moved.
4. **Due date decides what is in today's plan at all.** Only tasks due today or earlier are scheduled, so an unfinished task from yesterday carries forward and one queued for tomorrow waits.
5. **Completion removes a task from the plan** without removing it from the list.

I ranked them by asking what the cost of getting each one wrong is. Breaking the time constraint produces a plan the owner physically can't follow, so it can never bend. Priority is next because the whole point of dropping something is to drop the least important thing. A block preference is the cheapest to violate: a walk in the wrong window is a mild annoyance, while dropping the walk because its preferred window was full is a worse outcome, which is why the preference gives way and the task doesn't.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

**Conflict detection reports overlaps and leaves them alone, instead of resolving them.** `Scheduler.find_conflicts()` compares every pair of scheduled entries by start time plus duration and returns a list of warning messages. It makes two choices that each cost something.

*It checks overlapping durations, not just identical start times.* Comparing only start times would be a single pass with a set, but it would miss the common case: a 30-minute walk at 07:00 and a 15-minute brushing at 07:20 never share a start time and still collide. I confirmed this against the code: identical starts and partial overlaps are both caught, while a task that begins exactly as the previous one ends (07:30 against a walk ending 07:30) is correctly not a conflict. The price is pairwise comparison, which is quadratic in the number of tasks. I limited the damage by sorting by start time first, so the inner loop stops at the first task that begins after the current one ends and a clean plan costs close to one pass.

*It warns instead of fixing or crashing.* A conflict comes back as a message such as "Mochi is booked twice: 'Morning walk' 07:00-07:30 overlaps 'Brushing' 07:15-07:30", and the plan around it is kept. I did not raise an exception, because throwing away a whole day's plan over one double-booking is worse than the double-booking. I also did not try to move one of the tasks, because choosing which one to move is a scheduling decision, and the scheduler already has a place for those decisions. A second check that quietly made them differently would give two sources of truth about where a task goes.

I should be honest about what this feature is. `build_plan()` packs tasks one after another inside a block and blocks cannot overlap, so a plan it builds can never contain a conflict, and the check always comes back empty. The tradeoff there is deliberate: I prevent conflicts by construction and keep the detector as a guard for whatever changes the construction later, such as hand-assigned times or midnight-spanning blocks. To show it works I had to build overlapping entries by hand in `main.py`, which is also where I saw both pets and a single pet being flagged.

This is reasonable for the scenario because the scale is a household's day, tens of tasks at most, where quadratic cost is irrelevant and a clear warning is worth more than speed. It also cares about the owner rather than the pet: a conflict between two different pets is still flagged, since one person can't do both at once.

**A second, bigger tradeoff I accepted rather than solved:** packing is greedy. Tasks are placed in priority order into the first block with room, which is simple and easy to explain but not optimal. With a single 30-minute block, a high-priority 25-minute walk is placed and two medium 15-minute tasks are both dropped, although the two of them would have fit together and completed two tasks instead of one. That outcome follows my own ranking, where a higher priority beats a higher count, so I think it is the right call here, but it means the plan can leave time unused that a smarter packing would have filled.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used AI mostly for design brainstorming and for translating decisions into code once I had made them. It drafted the first UML, turned that diagram into dataclass stubs, and then filled in the scheduling logic in `pawpal_system.py` and the terminal script in `main.py`.

The most useful prompts weren't requests for code. Asking "what questions should I consider here?" before deciding something got me a list of tradeoffs to weigh instead of an answer I'd have accepted without understanding. Asking "why does this logic live here rather than there?" was similarly useful — it forced an explanation of the architectural rule being applied, which I could then judge on its own terms. Asking it to point out missing relationships or bottlenecks in the UML also surfaced a real gap I hadn't noticed: once an Owner could have multiple pets, nothing in the plan recorded which pet a task belonged to.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

Several times. The clearest was the `preferences` field on Owner: the first UML draft gave the owner a free-text preferences field, but nothing in the scheduling logic actually read it, and it wasn't stored in a format anything could use. I rejected the whole approach rather than asking for it to be wired up, because the information it was trying to capture — when the owner wants things to happen — is already expressed by time blocks and priority. I also caught that the draft's recurrence fields were meaningless in a single-day plan, since there was no concept of a next day for a weekly task to land on, and cut them rather than carry dead structure.

For verification, this first push was deliberately CLI-first. I ran `python main.py` and read the actual terminal output to confirm the sample household, task list, and generated schedule looked the way I expected — that tasks were sorted by priority, landed in their preferred blocks, and that the totals added up. I also checked edge cases by hand: a full preferred block correctly bumps a task elsewhere instead of dropping it, an oversized task gets dropped with a stated reason, and an empty block list doesn't crash. Then I wrote basic pytest tests covering task completion and task addition, to lock in that the data can be created, organized, and modified as intended.

That was enough to trust the core, not enough to call it verified, and I noted at the time that the tests only covered data handling. That has changed. The suite now has 54 tests, and what I said was missing has been written:

- **Data handling:** completing a task, adding a task, editing a task or pet without losing its completion status or pet link, removing a task or pet by identity, and rejecting blank names.
- **Household rules:** pet names must be unique, block labels must be unique, blocks can't overlap (though blocks that touch are fine), and renaming or removing a block updates the tasks that preferred it.
- **Sorting and filtering:** scheduled tasks come back in clock order, including the case where string order could have gone wrong with afternoon times; duration sorts both directions; and `filter_tasks()` narrows by pet, status, priority, block and due date, singly and combined.
- **Recurrence:** the next date for each frequency, unknown frequencies rejected on create and on edit, completing queues the next occurrence once and never twice, and Undo withdraws the queued occurrence unless it has been edited or completed in its own right.
- **Conflict detection:** two tasks at exactly the same time are flagged (same pet or different pets), partial overlaps are flagged with every pair listed, back-to-back tasks are not, the warning reaches `Plan.explain()`, and a plan built by `build_plan()` comes back clean.
- **The packing rules I used to check by eye:** a full preferred block moves a task to another block instead of dropping it, an oversized task is dropped with a stated reason, an empty block list or empty task list doesn't crash, a task that exactly fills a block fits while one more minute doesn't, and priority orders placement with shorter tasks first within a priority. One test also pins the greedy tradeoff from 2b, so changing it later has to be deliberate.
- **Validation and calendar edges:** bad task details and impossible time blocks are rejected, and recurrence crosses month, year and leap-day boundaries.
- **The Streamlit UI** (`test/test_app.py`, driven headlessly with Streamlit's `AppTest`): the plan stays on screen after a task is marked done, marking a daily task done queues tomorrow's and Undo takes it back, overlapping availability blocks the plan, deleting a pet asks first, a renamed block carries over to its tasks, and the filters and sort change what the list shows.

I checked that these tests can actually fail, not only that they pass. I broke the code on purpose in throwaway copies, ten ways in total, including sorting latest-first, a daily task queuing the same day, conflicts compared on start times only, touching tasks counted as conflicts, and the original plan-vanishes bug. Every one made at least one test fail.

What is still not covered: equal-length tasks in the duration sort (the stable-sort behaviour is only described in its docstring), the app's edit form for a task's frequency and due date (I drove it by hand but didn't commit a test), and the date itself. The UI tests use today's real date, so a run that straddled midnight could in principle fail one.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

The suite has 54 tests: 44 against the backend classes in `test/test_pawpal.py` and 10 that drive the Streamlit app headlessly in `test/test_app.py`. They fall into five groups.

1. **The scheduling algorithms.** Sorting returns clock order (including the afternoon case where text order could have gone wrong), recurrence queues the right next date for daily and weekly tasks, and conflict detection flags tasks at the same time and tasks that partly overlap while leaving back-to-back tasks alone. These are the features the project is built around, so they got the most direct tests.
2. **The packing rules.** A full preferred block moves a task instead of dropping it, an oversized task is dropped with a reason, empty inputs don't crash, a task that exactly fills a block fits while one more minute doesn't, and priority decides placement. I originally checked all of these by eye in the terminal, which meant a later change could break them without anyone noticing. Pinning them as tests was the most valuable step for the scheduler's reliability.
3. **Rules that keep the data honest.** Pet names and block labels must be unique, blocks can't overlap, blank names are refused, and a task can't be edited into a state it couldn't have been created in. These matter because the scheduler trusts its inputs. A duplicate pet name or two overlapping blocks doesn't crash anything, it just produces a plan that is quietly wrong, which is the worst kind of failure for a tool people rely on.
4. **Undo and cleanup paths.** Undoing a completion withdraws the queued occurrence unless it has been edited since, completing a task twice doesn't queue two copies, and renaming or removing a block updates the tasks that preferred it. Features like these tend to be right on the happy path and wrong on the second click, so I tested the second click.
5. **What the user actually sees.** The UI tests cover the plan staying on screen after a task is marked done (it used to vanish on the next click), overlapping availability blocking the plan, delete asking for confirmation, and the filters and sort changing the list. These bugs were found by using the app, not by reading the backend, so they needed tests at the app level.

I also checked that the tests can fail. Passing tests only mean something if they would have caught the bug, so I broke the code on purpose in throwaway copies, ten different ways, and confirmed each break made at least one test fail.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

**Confidence level: ★★★★☆ (4 out of 5).**

I'm confident in the scheduling logic itself. Every rule it applies is covered by a test, the required behaviors (sorting, recurrence, conflict detection) are covered more than once, and the deliberate breakage check shows the tests are sensitive to real mistakes, not just present. The suite passes in a few seconds, so it is cheap to run after every change.

I stopped at four because of what the tests can't see, not because I know of a failure:

- **The UI is tested through `AppTest`, not a real browser.** It proves the logic wired into the page works, but not how the page looks or whether a layout breaks at a different width.
- **The tests lean on today's date in the UI.** A test run that straddled midnight could fail one.
- **Nothing is saved between sessions.** Closing the app loses the household, which limits how much a daily recurring task can mean in practice.
- **The scheduler is greedy.** One test pins that behavior, but passing it only proves the plan follows my rule, not that the rule gives the best plan for every household.

The edge cases I would test next, roughly in order of how likely I think they are to expose something:

1. **Completing a task late.** The next occurrence is dated from the task's due date, not from when it was completed. A daily task due Monday and completed on Thursday queues one due Tuesday, which is already overdue. That might be right (the owner still owes those days) or wrong (they would rather start fresh), and I haven't decided or tested it.
2. **Time that is fragmented across blocks.** Tasks are never split, so two blocks with 10 free minutes each can't hold a 15-minute task even though 20 minutes are free. The task is dropped and the plan says so, but I haven't tested how often that happens with realistic data.
3. **Overnight availability.** A block like 22:00 to 02:00 is rejected as ending before it starts, which is accurate but unhelpful for someone with a night routine.
4. **Midnight rollover and a fixed clock.** Freezing the date in the UI tests would remove the flaky-at-midnight case and let me test "overdue" and "due tomorrow" at known dates.
5. **Equal-length tasks in the duration sort**, and **larger households.** Conflict detection is quadratic in the worst case, which is irrelevant for dozens of tasks, but I haven't run it on thousands to confirm.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
