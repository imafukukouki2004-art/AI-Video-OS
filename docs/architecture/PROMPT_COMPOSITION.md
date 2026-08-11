# Prompt Composition Foundation

TICKET-032 adds typed, runtime-only prompt composition without introducing a prompt library,
template persistence, versioning, optimization, or retrieval.

## Runtime contract

Workflow steps continue to use the existing provider configuration contract:

```json
{
  "provider": "mock",
  "operation": "text_generation",
  "system_prompt": "You are a concise video producer for {{audience}}.",
  "prompt": "Turn {{research.output}} into a shot list."
}
```

`PromptBuilder` converts the configured strings to typed `PromptTemplate` values, resolves
variables through the execution's `VariableResolver`, and returns a `PromptComposition`.
The runtime then passes `user_prompt` as the provider's `prompt` argument and, when present,
passes `system_prompt` through the provider's existing keyword arguments. The provider
interface is unchanged.

## Supported variables

- `{{step.output}}` — prior step output
- `{{step.artifact}}` — prior workflow artifact identifier
- `{{step.asset}}` — prior asset identifier
- `{{step.image}}` — prior stored image reference
- `{{variable}}` — runtime variables, including loop variables

Resolution fails before a provider call when any referenced value is unavailable. Image
generation uses the same user-prompt composition path and intentionally does not forward a
system prompt.

## Boundaries

Templates are value objects owned by the current workflow configuration. TICKET-032 does not
add template IDs, storage, discovery, versioning, optimization, RAG, or agent behavior.
