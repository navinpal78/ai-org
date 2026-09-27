# Skills for storyteller

One file per skill. Filename becomes the skill name.

A skill is a markdown file the agent reads when the task looks like it needs
it. Keep each one narrow: "how to run a database migration safely" is a skill.
"How to do engineering" is not, and will just add noise to every prompt.

Format: a short heading, the procedure as numbered steps, and a failure section
listing what goes wrong. That last part is the part that actually prevents
mistakes, and models that follow a checklist rarely skip a step.

Every skill you add should come with a test case in tests/cases.tsv. An agent
with skills and no tests is a guess.

---

## The two

- **`empty-story.md`** - the diagnosis. What "atmospheric prose in place of an
  event" looks like, the three questions, and the three fixes. Read this when a
  scene has been written and something about it feels thin.
- **`scene-and-structure.md`** - the shape. Want / obstacle / decision /
  consequence, what a turn actually is, why a twist has to be planted, and where
  long pieces sag. Read this before drafting anything long.

They are ordered the way the work arrives. The first answers "is this a story",
the second answers "does the story hold together", and the SOUL only points at
the first because the second is the one you should already know.

Neither is a style guide. Prose is the part of this job that needs least
supervision and the part that makes an empty story look finished, so the
supervision goes on the structure underneath it.
