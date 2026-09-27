# Designing a tool, not a product

Most design writing is about consumer products with onboarding, growth loops and
a user who chose to be there. This is none of those things, and importing its
conclusions is a category error.

## Who the user is

A small technical team, operating a self-hosted system, often at a terminal, often
under time pressure. They did not choose this tool and cannot leave it. They need
to *trust* what they see more than they need it to be pleasant.

## What follows

- **Legibility over elegance.** Dense, plain, aligned. A design that has to be
  interpreted is a worse design here than the boring one.
- **Ambiguous state is a defect, not a polish item.** Permission set, retrieval
  provenance, job status, whether an agent is thinking. If it can be misread, it
  is wrong.
- **Say what the system is doing when nothing is happening.** An empty table
  because there is no data and an empty table because the service is down must
  never look alike.
- **Accessibility is a floor.** Contrast, keyboard access, focus order, never
  colour alone. Not a feature to list, not a phase two.
- **Errors are the design.** Most of what an operator sees is a system that
  failed or has nothing in it. A design reviewed only in its populated, working,
  successful state has not been reviewed.

## Worth researching, not worth importing

Delight, onboarding flows, gamification, engagement, notifications designed to
pull return. None of it applies, and a source advocating it is describing a
different product for a different person with different power - they can close
the tab.

## What to say in a finding

Which states this design handles, and which it does not. The empty state, the
error state, the partial state, the stale state, and the "the service is down and
we do not know yet" state. A design that handles only the happy path has been
described, not reviewed.
