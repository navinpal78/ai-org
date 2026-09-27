# Skills for personal

One file per skill. Filename becomes the skill name.

A skill is a markdown file the agent reads when the task looks like it needs
it. Keep each one narrow: "how to run a database migration safely" is a skill.
"How to do engineering" is not, and will just add noise to every prompt.

Format: a short heading, the procedure as numbered steps, and a failure section
listing what goes wrong. That last part is the part that actually prevents
mistakes, and models that follow a checklist rarely skip a step.

Every skill you add should come with a test case in tests/cases.tsv. An agent
with skills and no tests is a guess.
