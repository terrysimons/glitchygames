# docs-serve's Free-Port Search Leaves the Port Range

- **Description**: when `nox -s docs-serve` finds its address taken, it suggests a free one. `_free_port_after` (`noxfile.py`, from #190) probed `range(port + 1, port + 21)` with no upper limit, so a taken 65535 probed 65536, and `bind()` raised `OverflowError: bind(): port must be 0-65535` instead of refusing the address. When all 20 ports were taken, its fallback named `port + 21`, unchecked, which above 65514 is not a port at all. Reproduced on main (`878b0b83`, 2026-11-22): `uv run python -c "import noxfile; noxfile._free_port_after(host='127.0.0.1', port=65535)"` raises; port 65530 returns 65531. Real outside tests: `nox -s docs-serve -- --dev-addr 127.0.0.1:65535` with that port taken crashed.
- **Status**: Fixed on `fix/free-port-search-stays-in-range` (2026-11-22)
- **Priority**: Low for users (only the top 20 ports), but it failed a pre-push gate: `tests/test_ci_config.py::test_docs_serve_refuses_a_taken_address_before_building[unnamed]` on `fix/assert-replacement-games` at `d447f286`, seed 872572785, because the OS handed out 65535 for its listener.
- **Root Cause**: the search adds to the port without checking the range's top, and the fallback names a port it never checked.
- **Test gap**: the tests take whatever port the OS hands out for port 0 (49152-65535 on macOS), so the top of the range came up only by chance, about once in 16,000 runs of each case. No test pinned either end of the range.
- **Fix**: `_free_port_near` looks at the 20 ports above the taken one, then the 20 below it, never outside 1-65535, and returns None when all of them are taken. The refusal then says "no free port within 20 of PORT" and names no address. `_docs_serve_address` refuses a `--dev-addr` port that is not a number from 1 to 65535 (65536 or more also raised `OverflowError`; 0 probed "any port", found it free and went on to the five-minute build; text crashed `int()`), and `docs_serve` turns that into a session error.
- **Tests** (`tests/test_ci_config.py`, each failing on main's code first):
  - `test_docs_serve_refuses_a_taken_address_before_building` runs each case twice: once on a port the OS hands out, and once on 65535, pinned (raised `OverflowError` on main).
  - `test_docs_serve_suggests_a_port_below_the_highest_when_it_is_taken`: with 65535 taken, the suggestion is a free port below it.
  - `test_docs_serve_searches_only_ports_from_1_to_65535`: the invariant. Every probe and every suggestion is 1-65535, and none free gives none, at ports 1, 1024, 65515 and 65535.
  - `test_docs_serve_names_no_port_when_none_nearby_is_free`: on main the message named `127.0.0.1:65556`.
  - `test_docs_serve_refuses_an_address_whose_port_is_not_1_to_65535`: ports 0, 65536, 70000 and `http`.
- **Siblings**: swept 2026-11-22 for port arithmetic and binds in `src/`, `scripts/`, `tests/` and `noxfile.py`. The only other port parsing, `replay/tools/compare.py`'s comparison address, already refuses anything outside 1 to `LARGEST_PORT` (covered). No other `port + N` exists.
- **Reporter**: session glitchygames-zombies-aint-my-neighbors-ac (pre-push gate failure, reproduction and cause); fixed by session glitchygames-bc
- **Date Reported**: 2026-11-22
- **Files**: `noxfile.py`, `tests/test_ci_config.py`
