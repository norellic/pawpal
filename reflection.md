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

**Recurrence.** My initial Task had `is_recurring` and `recurrence` fields, but since the plan only covers a single day, those fields had nothing to attach to — there was no concept of "tomorrow" for a weekly task to land on. I removed them rather than carry dead structure, and scoped the project explicitly to one day.

**Availability: one number became several blocks.** The Scheduler originally held a single `available_minutes` integer. That doesn't match how people actually have time — most owners have a morning window and an evening window, not one continuous span. I added a TimeBlock class (label, start, end) and changed `build_plan()` to take a list of them. That change cascaded: Task gained a `preferred_block` field, and ScheduledTask gained `block_label` so the plan can report where each task landed. I decided `preferred_block` is a soft preference, not a hard constraint — if the preferred block is full, the task still gets placed elsewhere rather than dropped.

**Completion.** Adding the ability to mark tasks done introduced a `completed` flag on Task, which raised a question I had to answer deliberately: should `get_all_tasks()` hide completed tasks? I decided no. A task history or mark-complete view would want the full list, and only the scheduler wants them excluded, so the filtering belongs at the call site rather than baked into data access. The deciding factor was which mistake is cheaper to undo — duplicating one filter line is easier to fix than unwinding a hidden filter that every future caller inherits.

**A gap I caught late.** Once an Owner could have multiple pets and tasks were flattened into a single list, nothing in the plan recorded which pet a task belonged to, so the output couldn't tell one dog's walk from another's. I added a `pet` back-reference on Task, set when `add_task()` is called.

**Deliberately deferred.** Priority ties currently break by shorter duration, which I flagged in the diagram as a rule to revisit. Recurrence stays out of scope, but I kept the seam where it would go: whatever decides which tasks are due today lives inside `get_all_tasks()`, so adding recurrence later shouldn't require changing Scheduler, Plan, or Task.

**The through-line.** Most of these changes came from asking the same question repeatedly: does this class actually need to know that detail, or can it just be handed a value? Keeping the Scheduler ignorant of Owner is why adding multi-pet support later cost almost nothing — I only had to change how the task list was assembled, not how it was scheduled.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

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

That's enough to trust the core, not enough to call it verified. The tests so far cover data handling rather than the scheduling algorithm itself, and the edge cases I checked were checked by eye in the terminal rather than pinned down as tests. Those are the next things to write as the functionality grows.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
