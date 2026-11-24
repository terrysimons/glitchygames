# A Zombies Pool Test Failed Once in a Pre-Push Gate and Has Not Failed Since

- **Description**: On 2026-11-24 the pre-push gate of `fix/paired-worker-close` (1b's branch, whose
  change touches only `scripts/ai_behaviour/paired.py`) failed in `nox -s test-random` on one test:
  `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_neighborhood.py::test_no_sprite_file_loads_during_play`,
  `assert scene.zombie_pool.given_back > 0` with `0 > 0` (line 964): in twenty busy seconds of play
  no zombie was handed back to its pool. The run was `--randomly-seed=3699576499
  --randomly-dont-reset-seed -n auto -m 'not wall_clock'` on the owner's Mac (Python 3.15.1), with
  worker `gw5` running the test as its 1,005th; it ended `1 failed, 31217 passed, 10 skipped,
  5 xfailed in 305.29s`. The next gate on the same branch (main merged in, `9b9957c5`) passed.
- **Status**: Open. Not reproduced; cause unknown.
- **Priority**: Low (one failure; it cost a gate run, about five minutes).
- **Root Cause**: Unknown. Ruled out, each by a run that passed:
  - the test alone (`-n0 --dummy-only`): 1 passed;
  - its whole file shuffled under the gate's seed (`-p randomly --randomly-seed=3699576499`):
    141 passed;
  - worker `gw5`'s exact sequence, the 1,005 tests up to and including the failure, serially in
    the gate's order (`-p no:randomly`): 1,005 passed;
  - the same sequence under the gate's seeding (`--randomly-seed=3699576499
    --randomly-dont-reset-seed --randomly-dont-reorganize`), so the global `random` state each test
    inherits is the gate's: 1,005 passed;
  - the engine's master seed: the harness gives every test unseeded streams
    (`tests/harness.py`, so `randomness.seed_engine_random` draws from `secrets.randbits(64)` and
    the test's `OPTIONS` give no `random_seed`), so each run of the test plays a different game.
    Under 200 fixed seeds (0 to 199) and 1,000 reproducible 64-bit seeds
    (`random.Random(20261124)`), injected by patching `randomness.secrets.randbits` (checked to
    reach `engine_random_seed()`): 1,200 passed;
  - wall-clock time: `run()` steps game time in fixed frames (`screen_support.tick_to`), so load
    cannot stretch the twenty seconds.

  What is left: something present only under the gate's full parallel load, or a master seed
  rarer than about 1 in 1,200 games.
- **Test gap**: The failure reports neither the master seed nor the pool's counters, so the
  failing game cannot be replayed. A test that plays an unseeded game and asserts that something
  happened in it is a property of the seed, checked on one seed per run.
- **Solution**: Not chosen. Next steps: (1) make the failure name its master seed
  (`randomness.engine_random_seed()`) and the pools' `taken`/`given_back` in the assert message, so
  the next failure can be replayed exactly; (2) then either pin the test's seed or assert the
  property over many seeds.
- **Known limits**: Only the owner's Mac was used for the reproduction attempts.
- **Sweep**: Not done yet: other tests that play an unseeded game and assert that an event
  happened.
- **Tests**: None yet.
- **Reporter**: The coordinator (Ledger), from the gate log of 1b's push.
- **Date Reported**: 2026-11-24
- **Files**: `src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_neighborhood.py`
  (`test_no_sprite_file_loads_during_play`, `busy_yard`, `run`),
  `src/games/zombies-aint-my-neighbors/tests/screen_support.py` (`tick_to`),
  `src/glitchygames/randomness.py`, `tests/harness.py`. The gate log and the triage plugins are in
  the coordinator's scratchpad (not kept); the method is recorded above.
