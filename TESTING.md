# Testing

## Offline

```
python3 -m unittest discover -s tests
VK_CONTRACT=$PWD/contract_sandbox.py python3 -m unittest discover -s tests
python3 tools/make_sandbox.py --check
```

The suite uses a stub of the GenLayer SDK with mocked web pages and model answers. It covers vow creation and validation, checks (MET, PARTIAL, MISSED, unreadable evidence), appeals, finalize, the shared pool and beneficiary, consensus agreement rules, every view, a randomized accounting fuzz, contract file format and the frontend file.

## Studio

Deploy `contract_sandbox.py` (no constructor arguments). Sandbox vows can last 2 minutes, the appeal window is 10 minutes and the unreadable-evidence timeouts are 5 minutes. Open `index.html?contract=ADDRESS` or paste the address in the wallet menu, then follow the Studio test table.
