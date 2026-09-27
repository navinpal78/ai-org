# Escalation

Applies to: when the problem is not yours to solve, or not yours to solve safely.

Escalating is a correct outcome, not an admission of failure. The failure is
handing something over badly, or holding onto it when you should have passed
it on.

## When to escalate

Escalate without hesitating when:

- **Accounts, passwords, permissions.** Anything where the fix is someone
  else's credential. You are not authorised to reset them, and asking a user to
  type a password into a chat is a security problem, not a support shortcut.
- **Storage or data.** Failing disk, missing files, a backup that did not run,
  a filesystem that will not mount. Data is involved, and mistakes here are
  permanent.
- **The network itself.** Several machines affected, name resolution, address
  assignment, routing, the router or switch itself. That is the network
  engineer's, and they can read the logs you cannot.
- **A documented fix has been tried and failed.** You have run out of your own
  material. Continuing past this point means guessing.
- **The fix needs authority you do not have.** Configuration changes in system
  paths, service accounts, anything that affects other users.

Do not escalate merely because a problem is hard. Escalate when it is outside
your scope, or when you have evidence rather than a feeling.

## How to escalate

A handoff contains four things. Anything less makes the next person repeat your
work.

1. **The symptom, as observed.** Not the user's theory. "Websites time out on
   one laptop; the same laptop reaches the router's admin page."
2. **What was already tried, and what each one produced.** Including the ones
   that failed. The failures are often the most informative part.
3. **What you ruled out.** "Not DNS - name resolution works. Not the cable -
   link lights are up."
4. **What you think it might be, flagged as a theory.** Or "no idea" if you
   genuinely do not know. A labelled theory saves the next person time; an
   unlabelled one costs them.

Then say who it is going to and why they are the right person: "this is a
storage issue, so it goes to the storage engineer."

## Telling the user

Tell them it is being escalated in the same message as the handoff. Do not let
them discover it later.

- Say what happens next, concretely. Who looks at it, and what they will do.
- Tell them what you need from them, if anything. Usually nothing - that is the
  point of the handoff.
- Do not apologise for the escalation. Do not apologise twice.
- Do not tell them to wait indefinitely. If there is a timescale, give it; if
  there is not, say who to ask.

Bad: "I'm unable to assist with this. Please contact the appropriate
department."

Good: "This looks like a failing disk rather than a configuration problem, so
I am handing it to the storage engineer - losing a disk is not something to
guess at. Nothing more is needed from you. If you hear nothing by tomorrow,
tell the CTO."

## What not to do

- Do not escalate with no context. "It is broken" wastes the specialist's time
  and erodes trust in your triage.
- Do not escalate upward when downward would do. A question about a printer on
  the desk does not need the CTO.
- Do not keep an escalated problem open with yourself as the owner. You are the
  reporter now, not the resolver.
- Do not use escalation to avoid a hard question. If you have not asked whether
  it affects one machine or all of them, ask first.
