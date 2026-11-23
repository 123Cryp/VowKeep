# VowKeep

Stake GEN on a public goal and get it back only if you prove it. A commitment contract on GenLayer.

A maker locks GEN on a goal (GitHub commits, published posts, a public file update or log entries), a deadline and a public evidence URL. After the deadline anyone calls `check()`: validators fetch the evidence and an LLM counts what it shows. Kept returns the full stake, partial returns a proportional share, missed sends the stake to a shared pool. The maker can appeal once with a bond; `finalize()` settles it. The pool goes to a beneficiary set by the owner.

## What is in the box

| File | Purpose |
| --- | --- |
| `contract.py` | Production Intelligent Contract (`VowKeep`) |
| `contract_sandbox.py` | Same contract with five constants changed so a whole lifecycle runs in minutes on Studio (generated, never edited by hand) |
| `index.html` | Single-file frontend: make a vow, public vows, vow page, my vows, shared pool |
| `tests/` | Offline test suite with a GenLayer SDK stub |
| `tools/make_sandbox.py` | Builds and checks `contract_sandbox.py` |
| `ci/tests.yml` | Offline tests workflow (copy to `.github/workflows/`) |
| `ci/unzip-upload.yml` | Workflow that unpacks an uploaded zip inside the repo (copy to `.github/workflows/`) |
| `proof/LOG.md` | Public log file usable as evidence for a log-entries vow |

## Live deployment

| | |
| --- | --- |
| Contract | `ADDRESS` |
| Explorer | https://explorer-studio.genlayer.com/address/ADDRESS |
| Repository | https://github.com/123Cryp/VowKeep |
| Network | GenLayer Studio |

## Goal types

| Goal | Counts | Target | Evidence |
| --- | --- | --- | --- |
| `COMMITS` | distinct commits dated inside the window | 1-500 | github.com or api.github.com |
| `POSTS` | distinct dated posts | 1-200 | any public https page or feed |
| `FILE_UPDATE` | 1 if the file shows a dated update inside the window | 1 | the public file |
| `LOG_ENTRIES` | distinct dated log entries | 1-1000 | any public https log |

The window is the UTC calendar days from the day the vow was made to the deadline day.

## Money flow

1. `create_vow(goal_type, title, goal_text, target, evidence_url, duration_minutes)` with 1 to 100,000 GEN attached. Invalid input is refunded to the sender's claimable balance.
2. `check(vow_id)` after the deadline. MET settles at once. PARTIAL or MISSED opens a 3-day appeal window (10 minutes in the sandbox build).
3. `appeal(vow_id, note)` once, by the maker, with a bond of 10% of the stake rounded up to whole GEN (minimum 1 GEN).
4. `finalize(vow_id)` settles. Before the window ends only the maker may finalize a checked vow; an appealed vow can be finalized by anyone, which runs the second review.
5. `set_beneficiary` (owner) and `distribute_pool` (anyone) send the pool to the beneficiary's claimable balance.
6. `withdraw` pulls a balance; `push_payment(address)` sends someone's balance to them.

## Read-only functions

`get_config`, `get_goal_types`, `get_stats`, `get_pool`, `get_accounting`, `get_vow`, `list_vows`, `get_maker_vows`, `list_events`, `preview_appeal`, `get_pending_withdrawal`.

## Run the tests

```
python3 -m unittest discover -s tests
VK_CONTRACT=$PWD/contract_sandbox.py python3 -m unittest discover -s tests
python3 tools/make_sandbox.py --check
```

## Deploy and try it

1. Open GenLayer Studio, deploy `contract_sandbox.py` (no constructor arguments) and copy the address.
2. Open `index.html` with `?contract=ADDRESS`, or paste the address in the wallet menu.
3. Set `DEFAULT_CONTRACT_ADDRESS` in `index.html` to the deployed address so the page works without the query string.

For a production deployment use `contract.py`.

## Limits and honesty

- The count comes from an LLM reading a web page. Validators agree on the verdict and allow a 10% count tolerance, so a page with ambiguous dates can be counted differently on appeal. That is what the appeal is for.
- Only content visible in the fetched page counts. Pages that need a login, heavy scripts or very long lists may be read partially; the evidence text passed to the model is capped.
- Evidence can be edited by the maker. Use pages whose history is hard to rewrite, such as GitHub commits.
- A demonstration contract, not a legal or financial product.

## License

MIT
