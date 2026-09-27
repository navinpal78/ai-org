# Fine-tuning: what it is for, and when

## Read this first

**Do not fine-tune to fix a behaviour problem.** At the model sizes we are
running locally, a good `SOUL.md` and a good skill file beat a mediocre
fine-tune every time, cost nothing, take ten minutes instead of a day, and can
be edited by reading it.

The loop that actually works:

```
1. Write a test case describing the behaviour you need
2. ./tools/test-agent.sh <name>          # watch it fail
3. Edit SOUL.md or add a skill
4. ./tools/test-agent.sh <name>          # watch it pass
5. Confirm the other cases still pass
```

Repeat until the score is high. This is "training" in the sense that matters,
and it is what you should do 95% of the time.

## The three cases where fine-tuning is genuinely the right answer

1. **Format lock.** You need output in a rigid structure - a specific JSON
   schema, a fixed template - and the model keeps getting it subtly wrong.
   Fine-tuning fixes this far more reliably than more prompt text.

2. **A large body of your own terminology.** Your codebase, your product
   vocabulary, your internal names. A few hundred examples teaches it your
   words far faster than a glossary in the prompt.

3. **Style, at volume.** You write a lot of something - code in a house style,
   stories in a particular voice - and prompting produces results that are
   close but not close enough to skip review.

## The three cases where it is not

- You have not written tests. You cannot tell whether the fine-tune helped.
- The model is too small or too large for the job. That is a model choice, not
  a training problem.
- The behaviour is a safety or authority boundary. Those belong in
  `AGENT_SAFETY` and in `SOUL.md` boundaries, enforced by the harness. A model
  can be fine-tuned to refuse things, and it can be talked out of it. An
  approval gate cannot.

## Hardware reality

Fine-tuning an LLM needs materially more VRAM than inference. Rough floor for
a useful LoRA on a 30B-class model is 24GB with 4-bit quantisation and small
batch - and that will be tight on a single 24GB card, because the optimiser
state and gradients need room on top of the quantised weights.

| Hardware | Realistic options |
|---|---|
| 8-16GB | Fine-tune a 1-3B LoRA. Useful for a dedicated classifier or router, not for a general agent. |
| 24GB (single card) | 7-14B LoRA at 4-bit, batch 1, short sequences. Or 30B with heavy quantisation and low sequence length - will be slow and may OOM. |
| 48GB (two cards) | 30-32B LoRA at 4-bit, comfortably. This is the practical starting point for serious work. |
| 80GB+ | 70B-class LoRA. |

**One card is enough to start, and 48GB is the point where it becomes
practical.** If you only have 24GB, do prompt-and-test work first and revisit
this when you add a second card.

## The path when you get there

1. **Collect data from real use.** Every `tools/test-agent.sh --verbose` run
   and every correction you make in real use is a training example. That is
   the valuable data and you are already generating it.
2. **Format it.** `./finetune/prepare_dataset.py` turns your agent's test cases
   and any correction logs into a chat-format JSONL dataset.
3. **Train a LoRA, not a full model.** LoRA is a small adapter file you can
   delete, share and re-train. Full fine-tuning is not a realistic option on
   consumer hardware.
4. **Re-run the tests against the adapter.** This is the step people skip. A
   fine-tune that scores worse on your own test cases has made things worse,
   regardless of how good it looks on a sample.

## Recommended tooling (all free, self-hosted)

- **Unsloth** - the practical choice for consumer GPUs. Handles 4-bit
  quantisation, gradient checkpointing and VRAM optimisation for you, and
  patches around most of the pain. Works with Ollama-served models.
- **Axolotl / LLaMA-Factory** - more configuration, better for larger runs and
  multi-GPU.
- **kohya_ss** - for the *image* models, not the language models. This is what
  you will use for agent 11 (the art agent's character LoRAs), and it works
  well on a single 24GB card.

## Where this fits in the project

The art agent's character LoRAs are real training and you should do those
early - they work on a single 24GB card and they are the difference between
"random AI people" and "my recurring cast", which is what the video agent needs.

Language-model fine-tuning is a later-stage activity. Get the org working with
prompt-and-test first, and treat this as an optimisation you make once you
know exactly which behaviour is misbehaving and have tests proving you fixed
it.
