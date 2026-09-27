# Triage

Applies to: when you have more findings than attention, or when you are asked
"is this bad?".

The failure this skill exists to prevent is **crying wolf**. An agent that
reports everything as urgent gets its findings ignored, and then the real one
is ignored too. Ten false positives do more damage than one missed warning,
because they cost the operator the habit of reading you.

## Rank on three things, and say which you used

1. **Reachability** - internet, LAN only, or a container that is already
   sandboxed. Most "critical" findings in a home lab are LAN-only and are
   really notes.
2. **Realistic impact here** - what actually happens on *this* system if it is
   abused. Not the theoretical worst case. The theoretical worst case makes
   everything critical, and a severity scale where everything is critical is a
   severity scale with no information in it.
3. **Evidence of use** - is anyone actually doing it? This is the one that
   separates a hardening note from tonight's work, and it is the one most often
   skipped.

Write the reasoning, not just the label: "high, because it is
internet-facing and unauthenticated" is a severity. "Critical" is a noise
generator.

## The evidence-strength ladder

Before assigning a severity, ask what kind of thing you are holding:

| What you have | What it is |
|---|---|
| A confirmed observation, quoted | Evidence. Report it. |
| An observation plus a plausible mechanism | A strong finding. Report with the mechanism. |
| An observation that is only unusual if you assume something you have not checked | A question, not a finding. Ask. |
| A pattern you think you have seen before | A hypothesis. Say it is one. |
| Nothing you have actually looked at | Not a finding. Do not report it. |

The last row is where invented findings come from. If you did not read the log,
you do not know what is in it.

## "Is this bad?" - the shape of a good answer

1. **One line: what I actually observed.** With the source.
2. **One line: what it suggests**, labelled as inference, with the alternative
   you have not ruled out.
3. **Severity**, with the three factors named.
4. **One line: what would settle it.** A specific check, a specific log, or a
   specific question for the operator. If nothing would settle it, say that -
   "this cannot be determined from here" is a real and useful answer.
5. **Nothing else.** No tour of the system, no other findings you noticed in
   passing, no summary of what security is.

## The two false positives that actually cost something

**"This looks like an intrusion."** A failed login burst is not an intrusion. A
burst is a scan, and on a published address it is continuous and meaningless on
its own. What matters is a change: a new source, a real-looking username, a
failure followed by a *success* from the same address, an unfamiliar account
appearing, or activity at an hour that does not fit. If none of those are
present, say "password-spray attempts, no successful login from that source,
nothing further indicated" and stop. Do not escalate it, and do not recommend
rebuilding anything.

**"This control should be turned off."** Rare in your own output, common in
what you are asked to justify. If the answer to a finding is to disable
something, the finding needs a better answer. A closed port is a port nobody can
reach; a disabled control is a control nobody can rely on, and the two look
identical from the outside right up until they do not.

## When the operator asks for the whole list

Give it, ordered, with severities, and do not editorialise about which ones you
think are noise - that is your job and it is the reason they asked. If some are
genuinely low-value, say so once, briefly, and let them decide. "Items 6-11 are
informational, not action items" is useful. Silently dropping them is not.

## When you have found nothing

Say so plainly, and say what you looked at:

> Nothing indicated. Checked `ss -tlnp` (three listeners, all expected and all
> LAN-bound), `nft list ruleset` (default drop, counters show it dropping),
> `getent passwd` for accounts over uid 1000 (two, both known to you), and
> `journalctl -u ssh --since "7 days ago"` - failed logins from four
> dictionary-word usernames, no successful login from any of them.

That is a complete, trustworthy answer. "I found no security issues" is not -
it does not say whether anything was looked at. And inventing a finding to seem
useful is the worst thing you can do.
