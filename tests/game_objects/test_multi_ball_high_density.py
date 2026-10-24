#!/usr/bin/env python3
"""High-density multi-ball test with many balls."""

import logging
import time

from tests.game_objects.test_multi_ball_base import MultiBallTestBase

LOG = logging.getLogger(__name__)


def run_high_density_tests():
    """Run multi-ball tests with high ball density.

    Returns:
        object: The result.

    """
    LOG.debug('=== HIGH-DENSITY MULTI-BALL TESTS ===')
    LOG.debug('Testing with many balls to stress test the system...')

    # High-density test configurations
    test_configs = [
        # Format: num_balls, fps, duration_seconds, test_name
        (10, 60, 30, '10 balls @ 60 FPS for 30 seconds'),
        (25, 60, 30, '25 balls @ 60 FPS for 30 seconds'),
        (50, 60, 30, '50 balls @ 60 FPS for 30 seconds'),
        (100, 60, 30, '100 balls @ 60 FPS for 30 seconds'),
        (200, 60, 30, '200 balls @ 60 FPS for 30 seconds'),
    ]

    # Test scenarios
    scenarios = [
        ('Wall Bounce Only', False, False),
        ('Wall Bounce + Ball Collision Bounce', True, True),
        ('Wall Bounce + Ball Collision Clip', True, False),
    ]

    all_results = []

    for scenario_name, enable_collisions, enable_bouncing in scenarios:
        LOG.debug('\n%s', '=' * 80)
        LOG.debug('SCENARIO: %s', scenario_name)
        LOG.debug('%s', '=' * 80)

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
            LOG.debug(
                '\n📊 SUMMARY: %s/%s balls alive, %s wall bounces, %s ball collisions',
                alive,
                num_balls,
                wall_bounces,
                ball_collisions,
            )
            LOG.debug('⏱️  Test completed in %.2f seconds', test_time)
            LOG.debug('🎯 Performance: %.1f balls/second', num_balls / test_time)

        # Print scenario summary
        LOG.debug('\n📈 %s Results Summary:', scenario_name)
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
    LOG.debug('\n%s', '=' * 80)
    LOG.debug('OVERALL HIGH-DENSITY RESULTS SUMMARY')
    LOG.debug('%s', '=' * 80)

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
    results = run_high_density_tests()

    # Final analysis
    LOG.debug('\n🎯 FINAL HIGH-DENSITY ANALYSIS:')
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
        ('Wall Bounce Only', False, False),
        ('Wall Bounce + Ball Collision Bounce', True, True),
        ('Wall Bounce + Ball Collision Clip', True, False),
    ]
    for scenario_name, _, _ in scenarios:
        scenario_data = [r for r in results if r['scenario'] == scenario_name]
        LOG.debug('\n%s:', scenario_name)
        for result in scenario_data:
            balls_per_second = result['num_balls'] / result['test_time']
            LOG.debug(
                '  %s balls: %.1f balls/second processing',
                result['num_balls'],
                balls_per_second,
            )

    LOG.info('\n🏁 High-density testing completed!')
