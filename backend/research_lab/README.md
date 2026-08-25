# Research lab (scratch code, not production)

Read this before touching anything in this folder, and before reviewing, cleaning,
or refactoring anything in it.

## What this is

Throwaway Python for testing one hypothesis from `docs/hypotheses/` — the code-side
counterpart to a working paper's observation log. Pull real numbers, try a
computation, hardcode an observed value, print a result. Nothing here is a product
feature.

## The two rules that make this safe

1. **Never imported by production code.** Nothing in `backend/main.py`,
   `backend/engine/`, or `backend/pipeline/` may import from `research_lab/`, ever.
   Deleting this entire folder must never break the running app or its tests. This
   is the actual thing that makes "endless, messy experiments" safe to allow.
2. **Never writes to the database.** No `sqlite3.connect`, no `backend.database`,
   no `INSERT`, ever — not even to a scratch table. Same reason a hypothesis stays
   as Markdown in `docs/hypotheses/` instead of DB rows before it concludes (see
   that folder's `README.md`): a hypothesis's evidence shape isn't decided yet, and
   a premature schema is worse than no schema.

## What's normal and expected in here

Hardcoded observed values, magic numbers, no docstrings, no type hints, no tests,
duplicated logic across files, files that only make sense next to the hypothesis
they support, files that grow large and ugly over weeks of checkpoints. None of
this needs fixing. Apply zero code-quality bar here — it would be wasted effort on
code whose only job is to get thrown away or rewritten properly at graduation.

## Agent behavior

Skip this folder in code review, cleanup passes, and "while I'm here" refactors by
default. Don't propose tests, types, or structure for it unless the user is
specifically asking about a hypothesis's status (e.g. "update the hypothesis,"
"is this one ready," "revoke this"). Treat a request that only touches a file here
plus its matching `docs/hypotheses/*.md` as a lightweight hypothesis-log commit,
not a change to review like production code — the two safety rules above are what
justify that.

## Naming

One file (or subfolder) per hypothesis, named to match its working paper, e.g.
`warsh_reaction_function.py` next to `docs/hypotheses/warsh-reaction-function.md`.
Never name a file `test_*.py` or `*_test.py` — that would pull it into `pytest`'s
default discovery, which this code is not written to survive.

## Graduation

When a hypothesis in `docs/hypotheses/` reaches a real conclusion, the real
implementation is written properly in `backend/engine/` and `backend/schema.sql`
from scratch, informed by what was learned here — not by promoting this file in
place. After that, the scratch file can be deleted or left as historical scratch;
either is fine, git history is the record.
