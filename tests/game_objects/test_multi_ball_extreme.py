#!/usr/bin/env python3
"""Extreme multi-ball test with maximum balls."""

import logging
import time

from tests.game_objects.test_multi_ball_base import MultiBallTestBase

LOG = logging.getLogger(__name__)


def run_extreme_tests():
    """Run multi-ball tests with extreme ball density.

    Returns:
        object: The result.

    """
    LOG.debug('=== EXTREME MULTI-BALL TESTS ===')
    LOG.debug('Testing with maximum balls to stress test the system to its limits...')

    # Extreme test configurations
    test_configs = [
        # Format: num_balls, fps, duration_seconds, test_name
        (500, 60, 20, '500 balls @ 60 FPS for 20 seconds'),
        (1000, 60, 20, '1000 balls @ 60 FPS for 20 seconds'),
        (2000, 60, 20, '2000 balls @ 60 FPS for 20 seconds'),
        (5000, 60, 20, '5000 balls @ 60 FPS for 20 seconds'),
    ]

    # Test scenarios - focusing on the most intensive ones
    scenarios = [
        ('Wall Bounce + Ball Collision Bounce', True, True),
        ('Wall Bounce + Ball Collision Clip', True, False),
    ]

    all_results = []

    for scenario_name, enable_collisions, enable_bouncing in scenarios:
        LOG.debug('\n%s', '=' * 100)
        LOG.debug('SCENARIO: %s', scenario_name)
        LOG.debug('%s', '=' * 100)

        scenario_results = []

        for num_balls, fps, duration, test_name in test_configs:
            LOG.debug('\n--- %s ---', test_name)

            # Create test instance
            test = MultiBallTestBase(
                test_name=f'{scenario_name} - {test_name}',
                num_balls=num_balls,
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
                'num_balls': num_balls,
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
                '\n📊 SUMMARY: %s/%s balls alive, %s wall bounces, %s ball collisions',
                alive,
                num_balls,
                wall_bounces,
                ball_collisions,
            )
            LOG.info('⏱️  Test completed in %.2f seconds', test_time)
            LOG.info('🎯 Performance: %.1f balls/second', num_balls / test_time)
            LOG.debug('🔥 Collision rate: %.1f collisions/second', ball_collisions / test_time)

        # Print scenario summary
        LOG.info('\n📈 %s Results Summary:', scenario_name)
        for result in scenario_results:
            LOG.debug(
                '  %s balls: %s/%s alive, %s wall bounces, %s ball collisions',
                result['num_balls'],
                result['alive'],
                result['num_balls'],
                result['wall_bounces'],
                result['ball_collisions'],
            )

    # Print overall summary
    LOG.debug('\n%s', '=' * 100)
    LOG.info('OVERALL EXTREME RESULTS SUMMARY')
    LOG.debug('%s', '=' * 100)

    for scenario_name, _, _ in scenarios:
        LOG.debug('\n%s:', scenario_name)
        scenario_data = [r for r in all_results if r['scenario'] == scenario_name]

        for result in scenario_data:
            LOG.debug(
                '  %s balls: %s/%s alive, %s wall bounces, %s ball collisions',
                result['num_balls'],
                result['alive'],
                result['num_balls'],
                result['wall_bounces'],
                result['ball_collisions'],
            )

    return all_results


if __name__ == '__main__':
    results = run_extreme_tests()

    # Final analysis
    LOG.info('\n🎯 FINAL EXTREME ANALYSIS:')
    LOG.debug('Total tests run: %s', len(results))

    # Check for any failures
    failures = [r for r in results if r['alive'] < r['num_balls']]
    if failures:
        LOG.debug('⚠️  %s tests had ball deaths', len(failures))
        for failure in failures:
            LOG.debug(
                '  - %s with %s balls: %s/%s balls alive',
                failure['scenario'],
                failure['num_balls'],
                failure['alive'],
                failure['num_balls'],
            )
    else:
        LOG.info('✅ All tests passed - all balls survived in all scenarios!')

    # Performance analysis
    LOG.debug('\n🚀 PERFORMANCE ANALYSIS:')
    scenarios = [
        ('Wall Bounce + Ball Collision Bounce', True, True),
        ('Wall Bounce + Ball Collision Clip', True, False),
    ]
    for scenario_name, _, _ in scenarios:
        scenario_data = [r for r in results if r['scenario'] == scenario_name]
        LOG.debug('\n%s:', scenario_name)
        for result in scenario_data:
            balls_per_second = result['num_balls'] / result['test_time']
            collisions_per_second = result['ball_collisions'] / result['test_time']
            LOG.debug(
                '  %s balls: %.1f balls/second, %.1f collisions/second',
                result['num_balls'],
                balls_per_second,
                collisions_per_second,
            )

    LOG.info('\n🏁 Extreme testing completed!')
