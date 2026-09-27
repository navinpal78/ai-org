# Reading a benchmark without being fooled

## A benchmark result is a fact about a benchmark

Not about the use case. The benchmark was built from someone's guess about what
matters, made by people who had never met the problem.

## Conditions that must travel with the number

- **Who ran it.** A neutral party, or the project's authors.
- **On what hardware.** Batch size, prompt length, quantisation, whether
  anything else was resident.
- **How many runs.** One sample is noise. Report variance when there is any.
- **On what task.** And is that task the reader's task?
- **Against what baseline.** A number without a comparator is not a result.

## The comparisons that look decisive and are not

- **Different quantisation.** A Q8 versus a Q4 comparison tells you about
  quantisation, not about the models.
- **Different context lengths.** Throughput collapses with context. A benchmark
  at 512 tokens says nothing about a 8k workload.
- **Synthetic tasks.** "MMLU went up 2 points" is a fact about MMLU.
- **Vendor-selected subsets.** Choosing the benchmark where you win is
  selection, and it is the most common way a number misleads.

## Language to distrust

- "State of the art" with no task and no comparator.
- "Up to 3x faster" - up to, under what conditions.
- "Seamless", "effortless", "dramatically" - marketing, not measurement.
- A chart with no error bars and no sample size.

## When a number is all you have

Give it, with every condition you were given, and say plainly that it is a single
vendor benchmark. A labelled weak source is useful. An unlabelled one is a trap
you have set for the next reader.
