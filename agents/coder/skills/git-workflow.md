# Git workflow

Applies to: any change to a repository.

## Before touching anything

1. `git status` — if the working tree is dirty, you did not make those changes.
   Ask before overwriting anything.
2. `git log --oneline -10` — match the existing commit style. Do not switch to
   a different convention mid-project.
3. `git branch --show-current` — know where you are. Never assume `main`.

## Branching

- One logical change per branch. If the request needs two unrelated fixes, say
  so and ask which to do first.
- Branch name from the request, lowercase with hyphens: `fix-session-timeout`.
- Do not commit directly to `main` unless told to.

## Committing

Write the message in the imperative, describing what the change does:

```
fix: expire session cookies after 30 minutes of inactivity

The session cookie had no max-age, so a closed browser kept the session
alive indefinitely. Set an explicit max-age in set_session_cookie() and
cover it with a test.
```

- First line under 72 characters, no trailing period.
- Explain *why* in the body when it is not obvious from the diff.
- Never `git commit -a` when you did not review what is staged.
- Do not amend or force-push unless explicitly asked. If a commit is wrong,
  make a new one; rewriting history someone else may have pulled is not your
  call.

## What goes in a commit

Only changes belonging to this task. Unrelated formatting, editor config
changes, or a file you happened to have open do not go in. If you notice
unrelated problems, mention them in your reply and leave them alone.

## Before you say it is done

```
git status          # anything unexpected still modified?
git diff            # read your own change
```

Then actually run the tests. Do not report success on a change you have not
run.

## Failure modes

- **Lost work:** `git stash` before any risky operation, and tell the user you
  did it. A stashed change is invisible to them.
- **Wrong branch:** `git branch --show-current` catches this. Do not switch
  branches with uncommitted changes without asking.
- **Amending someone else's commit:** if the last commit is not yours, do not
  amend. Make a new one.
- **Force push:** never, unless explicitly instructed by someone who knows what
  they are doing.
