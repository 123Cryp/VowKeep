# Architecture

## Contract

`contract.py` holds the `VowKeep` Intelligent Contract. One vow stores the maker, goal type, title, goal text, target, public https evidence URL, stake, deadline and status (`ACTIVE`, `CHECKED`, `APPEALED`, `SETTLED`).

- `check(vow_id)` runs after the deadline, callable by anyone. The leader fetches the evidence page with `gl.nondet.web.render`, then asks the LLM (`gl.nondet.exec_prompt`, JSON response) for `qualifying_count`. Code normalizes the answer (clamp to target, integer only) and derives the verdict itself: `MET` at or above target, `MISSED` at 0, otherwise `PARTIAL`.
- Equivalence: custom `gl.vm.run_nondet_unsafe`. A validator repeats the fetch and model call, requires the same status and verdict, and accepts counts within 10% of the target.
- Unreadable evidence records nothing; after the check timeout it counts as `MISSED`.
- `MET` settles at once. `PARTIAL` and `MISSED` wait for the appeal window, then `finalize` settles: MET returns all, PARTIAL returns `stake * count / target`, MISSED sends the stake to the shared pool.
- `appeal` (once, maker only, 10% bond rounded up to whole GEN) is reviewed by `finalize` with the maker's note in the prompt. A higher count upholds the appeal and refunds the bond; otherwise the bond goes to the pool and the first count stands.
- The owner sets the beneficiary. `distribute_pool` is callable by anyone and credits the beneficiary.
- Payments are pull-based (`withdraw`, `push_payment`). Rejected payable calls credit the attached value back instead of reverting.

Views: `get_config`, `get_goal_types`, `get_stats`, `get_pool`, `get_accounting`, `get_vow`, `list_vows`, `get_maker_vows`, `list_events`, `preview_appeal`, `get_pending_withdrawal`.

## Frontend

`index.html` is a single file using genlayer-js from esm.sh. Contract data reaches the page only as text nodes. Routes: Home, Make, Vows, one vow, Mine, Pool.
