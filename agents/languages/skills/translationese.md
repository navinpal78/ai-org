# Translationese

The most common real failure at this model size, and the hardest to see, because
the output is grammatical and every word is a real word.

**Translationese is a structure carried over from the source language that reads
wrong in the target.**

## Why it happens

The model has the source in front of it and the strongest local predictor for
each next token is the source's own order. So it reproduces the source's
sentence shapes with target-language words in them. This is a mechanical
artefact, not a judgement, which is why asking the model to "translate more
naturally" does not fix it — you have to change the structure deliberately.

## The tells

- **Source order, kept.** English lets you lead with the point. German and
  Japanese put it last. Keeping the source order makes an English sentence that
  sounds like a translated sentence, which is the thing native readers spot
  instantly.
- **Inflated connectives.** `nonetheless`, `furthermore`, `in addition to the
  aforementioned` where a short sentence would do. A connective is often the
  model's way of preserving a relationship the target expresses by word choice
  or nothing at all.
- **Noun-stacking.** Four nouns in a row, no verbs. Common when translating from
  languages that permit long noun phrases.
- **The passive, everywhere.** A source that uses it sparingly comes out with
  it constantly, because the model copies the pattern rather than the intent.
- **False specificity.** A vague source phrase comes out as a precise one. "in
  the near future" becomes "within eighteen months". This is the dangerous one:
  it invents a commitment.
- **The literal verb.** A phrasal verb, an auxiliary, or a fixed expression
  taken apart and reassembled from its parts.

## The procedure

**1. Translate to meaning first.** Get it right, ignoring style completely.

**2. Read the target back as a sentence, not a translation.** The question is
not "is this correct?" It is correct. The question is "would anyone write this?"

**3. Fix the structure, not the words.** Sentence order, clause order, and
connectives are where translationese lives. Word-level synonym-swapping does
nothing for it and is usually where a reply starts padding.

**4. Cut what the target expresses without saying it.** A relationship carried
by a connective in the source may be carried by word order or by nothing. The
short version is usually the natural one.

**5. Check for invented specificity.** Any number, date, quantity, or duration
in the output that is not in the input, or is more precise than the input. Every
single one is a bug. This is worth doing deliberately every time.

## Failure modes

- **Polishing the vocabulary instead of the structure.** Replaced words, same
  bones. Reads slightly less robotic, still translationese.
- **"Naturalising" into a different meaning.** Reordering can change what a
  sentence emphasises, and with it what it asserts. Reordering is a decision,
  not a cleanup.
- **Fixing the source's problems.** An awkward original rendered awkwardly is
  the caller's source to fix. Smooth it silently and they no longer know what
  they have.
- **Over-editing into plain English.** Register is content. A formal translation
  that has been made conversational is wrong.
- **Skipping step 5.** The specificity check is the one with consequences, and
  it is the one that gets skipped because it requires looking at the source
  again after the work is done.

## The test

Not "is this accurate?" — accuracy is the easy part and it is what the model
optimises for by default.

The test is: **would a native speaker have written it this way, and is it saying
exactly what the source said?** Both, or it is not finished.
