#!/usr/bin/env python3
"""Multi-ball tests at different frame rates."""

import logging
import time

from tests.game_objects.test_multi_ball_base import MultiBallTestBase

LOG = logging.getLogger(__name__)


def run_frame_rate_tests():
    """Run multi-ball tests at different frame rates.

    Returns:
        object: The result.

    """
    LOG.debug("=== MULTI-BALL FRAME RATE TESTS ===")
    LOG.debug("Testing multi-ball scenarios at different frame rates...")

    # Test configurations
    test_configs = [
        # (fps, duration_seconds, test_name)
        (30, 60, "30 FPS @ 60 seconds"),
        (60, 120, "60 FPS @ 120 seconds"),
        (120, 240, "120 FPS @ 240 seconds"),
        (float("inf"), 300, "Infinite FPS @ 300 seconds"),
    ]

    # Test scenarios
    scenarios = [
        ("Wall Bounce Only", False, False),
        ("Wall Bounce + Ball Collision Bounce", True, True),
        ("Wall Bounce + Ball Collision Clip", True, False),
    ]

    all_results = []

    for scenario_name, enable_collisions, enable_bouncing in scenarios:
        LOG.debug(f"\n{'=' * 60}")
        LOG.debug(f"SCENARIO: {scenario_name}")
        LOG.debug(f"{'=' * 60}")

        scenario_results = []

        for fps, duration, test_name in test_configs:
            LOG.debug(f"\n--- {test_name} ---")

            # Create test instance
            test = MultiBallTestBase(
                test_name=f"{scenario_name} - {test_name}",
                num_balls=5,
                enable_ball_collisions=enable_collisions,
                enable_ball_bouncing=enable_bouncing,
            )

            # Run test
            start_time = time.time()
            alive, wall_bounces, ball_collisions = test.run_test(fps, duration)
            test_time = time.time() - start_time

            # Store results
            result = {
                "scenario": scenario_name,
                "fps": fps,
                "duration": duration,
                "alive": alive,
                "wall_bounces": wall_bounces,
                "ball_collisions": ball_collisions,
                "test_time": test_time,
            }
            scenario_results.append(result)
            all_results.append(result)

            # Print summary
            LOG.info(
                f"\n📊 SUMMARY: {alive}/5 balls alive,"
                f" {wall_bounces} wall bounces,"
                f" {ball_collisions} ball collisions"
            )
            LOG.info(f"⏱️  Test completed in {test_time:.2f} seconds")

        # Print scenario summary
        LOG.info(f"\n📈 {scenario_name} Results Summary:")
        for result in scenario_results:
            fps_str = f"{result['fps']:.0f}" if result["fps"] != float("inf") else "∞"
            LOG.debug(
                f"  {fps_str} FPS: {result['alive']}/5 alive,"
                f" {result['wall_bounces']} wall bounces,"
                f" {result['ball_collisions']} ball collisions"
            )

    # Print overall summary
    LOG.debug(f"\n{'=' * 60}")
    LOG.info("OVERALL RESULTS SUMMARY")
    LOG.debug(f"{'=' * 60}")

    for scenario_name, _, _ in scenarios:
        LOG.debug(f"\n{scenario_name}:")
        scenario_data = [r for r in all_results if r["scenario"] == scenario_name]

        for result in scenario_data:
            fps_str = f"{result['fps']:.0f}" if result["fps"] != float("inf") else "∞"
            LOG.debug(
                f"  {fps_str} FPS: {result['alive']}/5 alive,"
                f" {result['wall_bounces']} wall bounces,"
                f" {result['ball_collisions']} ball collisions"
            )

    return all_results


if __name__ == "__main__":
    results = run_frame_rate_tests()

    # Final analysis
    LOG.info("\n🎯 FINAL ANALYSIS:")
    LOG.debug(f"Total tests run: {len(results)}")

    # Check for any failures
    failures = [r for r in results if r["alive"] < 5]
    if failures:
        LOG.debug(f"⚠️  {len(failures)} tests had ball deaths")
        for failure in failures:
            fps_str = f"{failure['fps']:.0f}" if failure["fps"] != float("inf") else "∞"
            LOG.debug(
                f"  - {failure['scenario']} @ {fps_str} FPS: {failure['alive']}/5 balls alive"
            )
    else:
        LOG.info("✅ All tests passed - all balls survived in all scenarios!")

    LOG.info("\n🏁 Frame rate testing completed!")
