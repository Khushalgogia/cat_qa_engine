# Notification Timings & What They Do — Complete Guide

> Last updated: 22 Feb 2026 · All times in IST · Verified from actual workflow YAML files and Python scripts

---

## ☀️ Morning Block (8:00 – 9:00 AM)
> Cortisol naturally peaks in the morning — best time to absorb new info and do high-speed recall.

| Time (IST) | Repo | Workflow | What It Does | Delivery |
| :--- | :--- | :--- | :--- | :--- |
| **08:17 AM** | `project99-repo` | `morning.yml` | **Vocabulary Email (Morning Dossier)** — ⚡ **Weekdays only.** AI generates 3 new GRE/CAT-level words with definitions, example sentences, and mnemonics. Saves words to a JSON database on GitHub. No new words on weekends — weekends are quiz-only. | 📧 Email only |
| **08:43 AM** | `cat_qa_engine` | `math_sprint.yml` | **Morning Math Sprint (Telegram)** — Sends 7 quick math questions as interactive Telegram buttons. Questions are picked based on your weak areas — if you got yesterday's problem wrong, it drills that category harder. Includes new categories: percent-to-fraction, approximate roots, fraction comparison, and successive percentages. | 📱 Telegram only |

> **Cron details:**
> - `morning.yml` → `47 2 * * 1-5` (02:47 UTC = 8:17 AM IST weekdays only)
> - `math_sprint.yml` → `13 3 * * *` (03:13 UTC = 8:43 AM IST daily)

---

## ☕ Mid-Morning Block (10:00 – 10:30 AM)
> Both verbal drills run daily, spaced 14 minutes apart to prevent task-fatigue. 

| Time (IST) | Days | Repo | Workflow | What It Does | Delivery |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **10:00 AM** | **Daily** | `verbal_drill` | `object_naming.yml` | **Object Naming Drill** — Picks 5 random objects from a 300+ word bank (tracks history to avoid repeats, resets when exhausted) and asks you to write 2 alternate names (aliases) for each. | 📱 Telegram + 📧 Email |
| **10:14 AM** | **Daily** | `verbal_drill` | `daily_grind.yml` | **Word Construction Drill** — Random task like "Write 4 words starting with 'K'" or "Write 6 words that are exactly 3 letters long." | 📱 Telegram + 📧 Email |

> **Cron details:**
> - `object_naming.yml` → `30 4 * * *` (04:30 UTC = 10:00 AM IST daily)
> - `daily_grind.yml` → `44 4 * * *` (04:44 UTC = 10:14 AM IST daily)

---

## 🏢 Mid-Day Block (1:00 – 2:30 PM)
> Deep work window (10:30 AM → 1 PM) is protected.

| Time (IST) | Repo | Workflow | What It Does | Delivery |
| :--- | :--- | :--- | :--- | :--- |
| **01:13 PM** | `wingman-repo` | `wingman.yml` | **Future Self Motivation (Single Daily Hit)** — AI pretends to be "You from 2027" who made it to IIM. Picks a vivid IIM life scenario (romance, placements, hostel nights, etc.) and writes a short, punchy Hinglish message. | 📱 Telegram + 📧 Email |
| **02:19 PM** | `project99-repo` | `afternoon.yml` | **Vocabulary Quiz (Telegram Polls + Email)** — Takes today's 3 morning words + 1 random old word ("cold case"), generates CAT-style MCQ for each, sends as interactive Telegram quizzes and formatted HTML email with answers. | 📱 Telegram + 📧 Email |
| **02:30 PM** | `cat_qa_engine` | `daily_problem.yml` | **Spot the Flaw Challenge (Telegram Poll)** — Shows a math problem with a step-by-step solution where ONE step has a hidden logical error. You vote on which step is wrong. If there are more than 10 steps, Gemini AI condenses them. | 📱 Telegram only |

> **Cron details:**
> - `wingman.yml` → `43 7 * * *` (07:43 UTC = 1:13 PM IST daily)
> - `afternoon.yml` → `49 8 * * *` (08:49 UTC = 2:19 PM IST daily)
> - `daily_problem.yml` → `0 9 * * *` (09:00 UTC = 2:30 PM IST daily)

---

## 🌆 Late Afternoon Block (6:30 – 7:00 PM)
> Charisma is kept to Mon/Wed and shifted later so you can speak out loud while commuting.

| Time (IST) | Days | Repo | Workflow | What It Does | Delivery |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **06:47 PM** | **Mon & Wed** | `charisma-repo` | `charisma.yml` | **Charisma Speaking Drill** — AI picks a random funny scenario and gives you a 5-minute verbal exercise. 3 types: Spin Doctor (reframing), Genre Mashup (explain tech in a genre), Shark Tank (sell useless objects). | 📱 Telegram + 📧 Email |
| **06:51 PM** | **Daily** | `rc-practice-repo` | `rc_practice.yml` | **Reading Comprehension Practice** — Fetches a real essay (Aeon, Nautilus, etc.), builds a CAT-style RC prompt, emails it with a one-click link to paste into Gemini for AI-graded practice. | 📱 Telegram + 📧 Email |

> **Cron details:**
> - `charisma.yml` → `17 13 * * 1,3` (13:17 UTC = 6:47 PM IST Mon & Wed)
> - `rc_practice.yml` → `21 13 * * *` (13:21 UTC = 6:51 PM IST daily)

---

## 🌙 Evening Block (7:30 – 8:00 PM)
> Third math sprint session and the evening study wind-down.

| Time (IST) | Repo | Workflow | What It Does | Delivery |
| :--- | :--- | :--- | :--- | :--- |
| **07:30 PM** | `cat_qa_engine` | `math_sprint_evening.yml` | **Evening Math Sprint (Telegram)** — Third and final sprint session of the day. Same format: 7 quick math questions with weak-area targeting and interactive buttons. | 📱 Telegram only |

> **Cron details:**
> - `math_sprint_evening.yml` → `0 14 * * *` (14:00 UTC = 7:30 PM IST daily)

---

## 🛌 Night: The Consolidation Window (9:49 – 10:13 PM)
> 24-minute gap between the two jobs prevents race conditions if GitHub Actions is lagging.

| Time (IST) | Repo | Workflow | What It Does | Delivery |
| :--- | :--- | :--- | :--- | :--- |
| **09:49 PM** | `cat_qa_engine` | `nightly_axiom.yml` | **Nightly Axiom (Telegram)** — Delivers a Cognitive Anchor tied to today's Spot the Flaw problem. 3-part format: Core Rule, Mental Model, and an Anchor Question. If you caught the flaw: "Lock it in." If you missed it: "Make sure it never gets you again." | 📱 Telegram only |
| **10:13 PM** | `cat_qa_engine` | `graveyard_nudge.yml` | **Graveyard Nudge (Telegram)** — Resurfaces an old problem you previously got WRONG. Shows the problem and asks you to mentally recall the trap. "Got It" / "Still Foggy" buttons. | 📱 Telegram only |

> **Cron details:**
> - `nightly_axiom.yml` → `19 16 * * *` (16:19 UTC = 9:49 PM IST daily)
> - `graveyard_nudge.yml` → `43 16 * * *` (16:43 UTC = 10:13 PM IST daily)

---

## 🏖️ Weekend Extras (Saturday & Sunday)

In addition to the daily schedule above, weekends also get:

| Time (IST) | Repo | Workflow | What It Does | Delivery |
| :--- | :--- | :--- | :--- | :--- |
| **12:00 PM** | `project99-repo` | `weekend.yml` | **Weekend Vocab Quiz** — Picks 4 random words from the entire word bank and generates CAT-style MCQ quizzes. Full revision mode. | 📱 Telegram + 📧 Email |
| **08:00 PM** | `project99-repo` | `weekend.yml` | **Weekend Vocab Quiz (2nd round)** — Same as 12 PM, fresh set of 4 random words. | 📱 Telegram + 📧 Email |
| **08:30 PM** | `cat_qa_engine` | `weekly_report.yml` | **Weekly Report Card** — 🔴 **Sundays only.** Summarizes your week: problems caught vs missed, blind spots by error category, strengths, sprint stats (answers, correct rate, debt repaid, slowest category). | 📱 Telegram only |

> **Cron details:**
> - `weekend.yml` → `30 6 * * 0,6` (12:00 PM IST) and `30 14 * * 0,6` (8:00 PM IST) — Sat & Sun
> - `weekly_report.yml` → `0 15 * * 0` (15:00 UTC = 8:30 PM IST Sundays only)

> **Note:** Object Naming and Word Construction run **daily** (including weekends). Charisma drill is **Mon & Wed only**.

---

## 📊 Summary by Repo

| Repo | What It Does (Big Picture) | Notifications/Day |
| :--- | :--- | :--- |
| `cat_qa_engine` | CAT math — 2× daily sprints (7 Qs each), flaw detection, axioms, graveyard, weekly report | 5/day + 1 Sunday report |
| `charisma-repo` | Speaking/charisma exercise | 2/week (Mon & Wed) at 6:47 PM |
| `project99-repo` | Vocabulary — learn 3 new words mornings, get quizzed afternoons | 2/weekday, 4/weekend day |
| `rc-practice-repo` | Reading Comprehension with real essays | 1/day |
| `verbal_drill` | Verbal fluency — object naming (5:33 PM) + word construction (5:47 PM) | 2/day |
| `wingman-repo` | Emotional motivation — "Future Self" IIM scenarios | 1/day |

---

## 📅 Full Day Timeline (Weekday)

```
08:17 AM  📧  Vocabulary Email (project99-repo)
08:43 AM  📱  Morning Math Sprint — 7 Qs (cat_qa_engine)
10:00 AM  📱📧 Object Naming Drill (verbal_drill)
10:14 AM  📱📧 Word Construction Drill (verbal_drill)
01:13 PM  📱📧 Future Self Motivation (wingman-repo)
02:19 PM  📱📧 Vocabulary Quiz (project99-repo)
02:30 PM  📱  Spot the Flaw (cat_qa_engine)
06:47 PM  📱📧 Charisma Drill [Mon & Wed only] (charisma-repo)
06:51 PM  📱📧 RC Practice (rc-practice-repo)
07:30 PM  📱  Evening Math Sprint — 7 Qs (cat_qa_engine)
09:49 PM  📱  Nightly Axiom (cat_qa_engine)
10:13 PM  📱  Graveyard Nudge (cat_qa_engine)
```

**Total weekday notifications:** 11 (+ Charisma on Mon/Wed = 12)
**Total weekend notifications:** 10 (+ Weekly Report on Sunday = 11)

---

## 📅 Full Day Timeline (Weekend)

```
08:43 AM  📱  Morning Math Sprint — 7 Qs (cat_qa_engine)
10:00 AM  📱📧 Object Naming Drill (verbal_drill)
10:14 AM  📱📧 Word Construction Drill (verbal_drill)
12:00 PM  📱📧 Weekend Vocab Quiz — Round 1 (project99-repo)
02:30 PM  📱  Spot the Flaw (cat_qa_engine)
06:51 PM  📱📧 RC Practice (rc-practice-repo)
07:30 PM  📱  Evening Math Sprint — 7 Qs (cat_qa_engine)
08:00 PM  📱📧 Weekend Vocab Quiz — Round 2 (project99-repo)
08:30 PM  📱  Weekly Report Card [Sundays only] (cat_qa_engine)
09:49 PM  📱  Nightly Axiom (cat_qa_engine)
10:13 PM  📱  Graveyard Nudge (cat_qa_engine)
```

**Total weekend notifications:**
- Saturdays: 10
- Sundays: 11 (includes Weekly Report)

---

## 🔄 What Changed (vs. Previous Report)

| Change | Old | New |
| :--- | :--- | :--- |
| Spot the Flaw timing | 8:07 PM (evening) | **2:30 PM** (mid-day) |
| Verbal Drills timing | 5:33 & 5:47 PM | **10:00 & 10:14 AM** |
| Math Sprint frequency | 1× daily (morning only) | **2× daily** (morning + evening) |
| Math Sprint question count | 5 questions per sprint | **7 questions** per sprint |
| Deleted workflow: `math_sprint_afternoon.yml` | 2:30 PM IST daily | Replaced by Spot the Flaw |
| New workflow: `math_sprint_evening.yml` | — | **7:30 PM** IST daily |
| New sprint categories | — | `pct_to_fraction`, `approx_root`, `fraction_compare`, `successive_pct` |
| Axiom format | Plain text | **Cognitive Anchor** (Core Rule + Mental Model + Anchor Question) |
| Total daily cat_qa_engine notifications | 4/day | **5/day** |
