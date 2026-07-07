# Rules for AI agents working on this repo
- NEVER modify evaluation logic (src/evaluate.py) to change what counts as success:
  no excluding claims from scoring, no "indeterminate" buckets, no coverage filtering.
  All 660 claims are always scored.
- NEVER change decision thresholds, prompts, or engine logic with the goal of
  improving metrics. Detection improvements must come from better reasoning or
  better rules, and must be explained in the commit message.
- NEVER read ground-truth fields (fraud_indicator, fraud_type) in any detection path.
- Any change that affects reported metrics must be listed explicitly in the commit
  message with before/after numbers.
- Commit after every task with a descriptive message. Never rewrite git history.