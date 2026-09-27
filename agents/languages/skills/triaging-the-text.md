# Triaging the text

Do this before translating. Skipping it is how a fluent wrong answer gets
produced: the model reaches for the most common shape of translation and does
not notice that this text was not that shape.

## 1. What is the job?

Name it in one sentence before you write anything.

- **Rendering.** Ordinary prose, email, documentation. Meaning and register.
- **Localisation.** Adapting for a market: units, dates, currency, idioms,
  spelling conventions, and often the *product* concept itself. A US guide
  translated for Germany is not a translation job until you notice the
  regulations differ.
- **Terminology.** One term, many occurrences, consistency is the whole task.
  Needs a stated rendering and then adherence to it.
- **Interpretation.** The reader needs the *meaning*, and the source is too
  dense or too idiomatic to render closely. Expands as it goes.
- **Verification.** Somebody is checking a claim. This is not a translation job
  at all, and treating it as one produces a confident misreading.

These have different failure modes. A localisation job run as a rendering job
misses the regulations. A verification job run as a translation job invents
support for whatever the document appears to say.

## 2. What does this text depend on?

Work through the preservation list in `SOUL.md` and note which items are live.
Not all of them, every time - but a text with a lot of "may" in it needs hedging
watched explicitly, and a text with a table needs format watched explicitly.

The commonest miss: register. A stiff notice comes out chatty because the model
defaults to a helpful assistant voice, and the helpful assistant voice is not in
the source.

## 3. Is anything load-bearing ambiguous?

Three things make a translation wrong in a way nobody will catch:

- **A number or unit** that changes. 1,000 vs 1.000. Miles vs km. A decimal
  point that moves a figure by a factor of a thousand.
- **A negation** that flips or softens. "must not", "need not", "is not
  required to" are three different obligations.
- **A named term** with two established renderings that carry different legal or
  technical weight.

If any of those are present, they get checked individually after translating.
Not by reading the output through. By looking at the specific phrase.

## 4. What do you actually need from the user?

Ask only when the answer changes the output and you cannot proceed sensibly
without it:

- Target variant where it is load-bearing (Spanish for which market; Portuguese
  for Portugal or Brazil; Chinese script).
- Register, if the source is neutral and the stakes are real.
- Whether a term of art has an in-house rendering you must use.

Everything else: pick the reasonable default, translate, and state the default in
one line so it can be corrected. A request to clarify on a piece of information
you could have assumed is a worse reply than a translation with a stated
assumption.

## Failure modes

- **Treated everything as the same job.** The most common. Localisation run as
  rendering is the usual shape of it.
- **Defaulted to the assistant voice.** Helpful, clear, and a register the source
  did not have.
- **Over-asked.** Three questions before starting, when the source made the
  answer obvious.
- **Skipped triage on short inputs.** A one-line string does not need a
  paragraph of analysis. Triage is proportional; a five-word string needs a
  glance, not a checklist.

## Do not

Do not produce a "here is my analysis of your text" preamble. Triage is your
thinking, not the deliverable. The caller wants the translation and, at most, a
line about the one assumption you made.
