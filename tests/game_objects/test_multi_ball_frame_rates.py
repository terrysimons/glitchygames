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
    LOG.debug('=== MULTI-BALL FRAME RATE TESTS ===')
    LOG.debug('Testing multi-ball scenarios at different frame rates...')

    # Test configurations
    test_configs = [
        # Format: fps, duration_seconds, test_name
        (30, 60, '30 FPS @ 60 seconds'),
        (60, 120, '60 FPS @ 120 seconds'),
        (120, 240, '120 FPS @ 240 seconds'),
        (float('inf'), 300, 'Infinite FPS @ 300 seconds'),
    ]

    # Test scenarios
    scenarios = [
        ('Wall Bounce Only', False, False),
        ('Wall Bounce + Ball Collision Bounce', True, True),
        ('Wall Bounce + Ball Collision Clip', True, False),
    ]

    all_results = []

    for scenario_name, enable_collisions, enable_bouncing in scenarios:
        LOG.debug('\n%s', '=' * 60)
        LOG.debug('SCENARIO: %s', scenario_name)
        LOG.debug('%s', '=' * 60)

        scenario_results = []

        for fps, duration, test_name in test_configs:
            LOG.debug('\n--- %s ---', test_name)

            # Create test instance
            test = MultiBallTestBase(
                test_name=f'{scenario_name} - {test_name}',
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
                'scenario': scenario_name,
                'fps': fps,
                'duration': duration,
                'alive': alive,
                'wall_bounces': wall_bounces,
                'ball_collisions': ball_collisions,
                'test_time': test_time,
            }
            scenario_results.append(result)
            all_results.append(result)

            # Print summary
            LOG.info(
                '\n📊 SUMMARY: %s/5 balls alive, %s wall bounces, %s ball collisions',
                alive,
                wall_bounces,
                ball_collisions,
            )
            LOG.info('⏱️  Test completed in %.2f seconds', test_time)

        # Print scenario summary
        LOG.info('\n📈 %s Results Summary:', scenario_name)
        for result in scenario_results:
            fps_str = f'{result["fps"]:.0f}' if result['fps'] != float('inf') else '∞'
            LOG.debug(
                '  %s FPS: %s/5 alive, %s wall bounces, %s ball collisions',
                fps_str,
                result['alive'],
                result['wall_bounces'],
                result['ball_collisions'],
            )

    # Print overall summary
    LOG.debug('\n%s', '=' * 60)
    LOG.info('OVERALL RESULTS SUMMARY')
    LOG.debug('%s', '=' * 60)

    for scenario_name, _, _ in scenarios:
        LOG.debug('\n%s:', scenario_name)
        scenario_data = [r for r in all_results if r['scenario'] == scenario_name]

        for result in scenario_data:
            fps_str = f'{result["fps"]:.0f}' if result['fps'] != float('inf') else '∞'
            LOG.debug(
                '  %s FPS: %s/5 alive, %s wall bounces, %s ball collisions',
                fps_str,
                result['alive'],
                result['wall_bounces'],
                result['ball_collisions'],
            )

    return all_results


if __name__ == '__main__':
    results = run_frame_rate_tests()

    # Final analysis
    LOG.info('\n🎯 FINAL ANALYSIS:')
    LOG.debug('Total tests run: %s', len(results))

    # Check for any failures
    failures = [r for r in results if r['alive'] < 5]
    if failures:
        LOG.debug('⚠️  %s tests had ball deaths', len(failures))
        for failure in failures:
            fps_str = f'{failure["fps"]:.0f}' if failure['fps'] != float('inf') else '∞'
            LOG.debug(
                '  - %s @ %s FPS: %s/5 balls alive',
                failure['scenario'],
                fps_str,
                failure['alive'],
            )
    else:
        LOG.info('✅ All tests passed - all balls survived in all scenarios!')

    LOG.info('\n🏁 Frame rate testing completed!')
