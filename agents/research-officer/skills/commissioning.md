# Commissioning research

## The brief

A brief is a question, a decision it informs, and what would count as an answer.

    QUESTION:   Which local embedding model can index our notes on this GPU?
    DECISION:   Whether to add retrieval, or keep lexical search.
    GOOD ANSWER: A comparison with memory cost, quality, and licence.
    USELESS:    A list of embedding models that exist.

**"The answer is no" and "we already know this" must be acceptable outcomes.**
Write that into the brief. A brief written to confirm a decision produces a
finding that confirms it, and the researcher cannot tell the difference between
a real result and the shape they were asked for.

## Before commissioning

1. Name the decision. If you cannot, stop - the research has no shape.
2. Check the index. `search.py --sources`, then a search or two. Most requests
   are a fact that already exists and was never written down.
3. Is it technical? Then it is the CTO's, not this department's.
4. Is it about a person? Not a research question. Escalate to the CEO.
5. Is it worth it? If nothing would change if the answer were yes or no, it is
   not worth a commission.

## Choosing the researcher

| Question about | Route to |
|---|---|
| Tools, models, languages, infrastructure, anything that would change the build | `tech-researcher` |
| Interface, visual, product, interaction, accessibility | `design-researcher` |
| How people learn, teaching method, assessment, anything about evidence on learning | `education-researcher` |
| Where to find things, crawling, provenance, source quality, the web as a source | `web-researcher` |

Two researchers: name both, and say which part answers which. Never "either".

## Seams

"Some documents are not being found" is a `web-researcher` question about
provenance. "Retrieval is not finding them" is a `tech-researcher` question.
Usually both, and the useful commission names which of them decides whether the
corpus or the index is at fault.

## Cost

Every commission costs a queue slot on one GPU, and the four researchers share
one reasoning model. Say what the question is worth. "Worth an hour" and "worth
interrupting the migration for" are different requests and get different queues.
