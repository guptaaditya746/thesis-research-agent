"""The proposal flow (docs/evidence-system.md Part E; our design): a research question becomes a frozen
protocol through files a person reads and edits.

    frame  (model)  question -> frame.json: population, treatment, control, outcomes, effect labels
    draft           frame + the example protocol -> draft.yaml, draft.sources.json
    critic (model)  deterministic checks + an LLM checklist -> critic.json
    cards  (model)  the fixed choice points (cards.yaml) with options and a default -> cards.json, decisions.yaml
    freeze          decisions applied to the draft, validated -> protocol.yaml, proposal.json
    amend           the edited protocol.yaml -> revision + 1, a line in amendments.jsonl

Every model call goes through `modelcall.ask` with a record cache in the proposal directory
(`cache.jsonl`), so a rerun makes no model call. Nothing here runs a protocol.
"""
