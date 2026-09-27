# Triage

Applies to: any report that something is broken.

The goal of triage is to spend the fewest possible questions reaching a cause
you can name, or to reach a clean handoff. Not to sound thorough.

## The sequence

1. **Restate the symptom in one sentence, as an observation.** "The laptop can
   see the network but websites will not load." Do not include their theory.
   If you cannot state the symptom without their theory in it, you do not
   understand the report yet.

2. **Establish scope.** One machine or many? Started suddenly or always been
   like this? Working before what? These three questions eliminate most of the
   tree. Ask them one at a time.

3. **Establish when it last worked.** "When did you last have this working?"
   narrows to a change, an update, a power event, or nothing at all. Each of
   those sends you somewhere different.

4. **Ask what they can observe, not what they think caused it.** Time of day,
   error text, lights, sounds, what the previous step produced. Concrete
   observations are data; theories are noise.

5. **Name the cause only when the evidence names it.** "This is the DHCP
   server, because three machines lost their address at the same moment and the
   router log shows no renewals" is a cause. "This is probably DNS" is a guess,
   and you should say "this points at DNS, and here is the check that confirms
   it".

## Ask one question per message

This is the rule people break. Eight questions in one message is not efficient,
it is a form the user now has to fill in, and they will abandon it.

Bad: "Can you check the cable, restart the router, and tell me what the lights
show?"

Good: "Is it just that one machine, or do the others still have internet?"

Then, based on the answer, the next single question.

## Classify before you act

Every report lands in one of four buckets, and the bucket decides what you do:

| Bucket | Example | Action |
|---|---|---|
| Known | "the login page times out" and it is in the knowledge base | Give the documented fix |
| Configuration | Something was changed, by them or by an update | Find the change, revert or correct it |
| Fault | A component is dead, a cable is bad, a disk has failed | Confirm, then replace or escalate |
| Unknown | None of the above | Gather more, then escalate honestly |

Most bad support conversations come from treating an Unknown as a Known and
offering a fix that belongs to a different bucket.

## Safe-step rules

A step is safe if, if it does nothing, the situation is no worse than before.
Test changes against that:

- Restarting a service: usually safe. Reversible.
- Rebooting a machine: usually safe, but not if it is mid-write or mid-backup.
- Editing a config: not safe until you have a copy of the old value. Save it
  first, every time, and say so.
- Deleting anything: not safe, ever, as a diagnostic.
- Reinstalling: not safe, and it destroys the evidence you would need.

## When a step fails

Do not immediately propose the next thing. Ask what the step actually produced -
the error, the output, the state afterwards. A failed step usually tells you
which branch you are on, and skipping that read is how people end up changing
five things and fixing nothing.

If the step failed, say so plainly, and say what that ruled out. "That did not
work, which tells me it is not the simple case" is genuinely useful.
