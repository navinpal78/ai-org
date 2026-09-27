# Feasibility for this organisation

A finding is only useful if it lands on something this setup can actually do.

## The envelope

- One RTX A5000, **24GB VRAM**. One card, shared - agents queue behind each other.
- Local inference. No cloud, no API keys, no bill. Ever, in the answer.
- Budget under $600, secondhand parts. A second machine is a different answer.
- Small team, often at a terminal, often under time pressure.

## Sizing, roughly

| Model | Q4 | Q8 | Verdict |
|---|---|---|---|
| 8B | ~5GB | ~9GB | Fits comfortably. Room for a second. |
| 14B | ~9GB | ~13GB | Fits. Watch the context length. |
| 27B | ~17GB | ~27GB | Q4 fits with ~2-3GB spare - one agent at a time only. |
| 32B | ~20GB | ~34GB | Q4 borderline, Q8 does not fit. |

Plus KV cache, which grows with context and is not in the table above. A 27B at
Q4 that "fits" has almost no headroom, and the first long context fills it.

## Questions to ask of any recommendation

1. **What does it replace?** If nothing, it is a cost.
2. **What is the latency?** ~5 tokens/sec per token of thinking. 1200 tokens of
   reasoning is minutes. If a human is waiting, that is the answer.
3. **What is the licence?** Weights and code differ. "Open source" covers
   Apache 2.0 through to terms forbidding what we would do.
4. **Is it maintained?** No commits in two years is a risk to name.
5. **What is the fallback?** If it disappears, what breaks?

## The baseline nobody has

No agent has a real score yet. So "better than the current model" has no current
model. Say that rather than accepting the comparison, and ask what the number
would be measured against.

## Answer shape

    Finding:   what the sources establish, with conditions attached
    Assessment: what it means for 24GB, one GPU, no cloud, $600
    Confidence: what would change your mind
