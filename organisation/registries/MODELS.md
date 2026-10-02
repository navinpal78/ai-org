# Model Registry

The model registry records models separately from agent identity and runtime.

No organisational role is permanently tied to a specific model.

Models may be local, hosted, hybrid or externally provided when approved for
the relevant workload.

## Model Independence

Changing the model must not require changing:

- agent identity;
- role definition;
- governance;
- organisational hierarchy;
- project identity.

Model requirements should be expressed in terms of capability, context,
quality, latency, cost, privacy, availability and other relevant constraints.

Model execution may depend on particular infrastructure or accelerators, but
those dependencies belong to the runtime/infrastructure layer.

No particular GPU, accelerator, CUDA stack, ROCm stack or hardware vendor is
an organisational requirement.
