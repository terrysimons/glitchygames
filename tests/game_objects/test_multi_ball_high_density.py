#!/usr/bin/env python3
"""High-density multi-ball test with many balls."""

import time
from test_multi_ball_base import MultiBallTestBase

def run_high_density_tests():
    """Run multi-ball tests with high ball density."""
    print("=== HIGH-DENSITY MULTI-BALL TESTS ===")
    print("Testing with many balls to stress test the system...")
    
    # High-density test configurations
    test_configs = [
        # (num_balls, fps, duration_seconds, test_name)
        (10, 60, 30, "10 balls @ 60 FPS for 30 seconds"),
        (25, 60, 30, "25 balls @ 60 FPS for 30 seconds"),
        (50, 60, 30, "50 balls @ 60 FPS for 30 seconds"),
        (100, 60, 30, "100 balls @ 60 FPS for 30 seconds"),
        (200, 60, 30, "200 balls @ 60 FPS for 30 seconds"),
    ]
    
    # Test scenarios
    scenarios = [
        ("Wall Bounce Only", False, False),
        ("Wall Bounce + Ball Collision Bounce", True, True),
        ("Wall Bounce + Ball Collision Clip", True, False)
    ]
    
    all_results = []
    
    for scenario_name, enable_collisions, enable_bouncing in scenarios:
        print(f"\n{'='*80}")
        print(f"SCENARIO: {scenario_name}")
        print(f"{'='*80}")
        
        scenario_results = []
        
        for num_balls, fps, duration, test_name in test_configs:
            print(f"\n--- {test_name} ---")
            
            # Create test instance
            test = MultiBallTestBase(
                test_name=f"{scenario_name} - {test_name}",
                num_balls=num_balls,
                enable_ball_collisions=enable_collisions,
                enable_ball_bouncing=enable_bouncing
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
                'test_time': test_time
            }
            scenario_results.append(result)
            all_results.append(result)
            
            # Print summary
            print(f"\n📊 SUMMARY: {alive}/{num_balls} balls alive, {wall_bounces} wall bounces, {ball_collisions} ball collisions")
            print(f"⏱️  Test completed in {test_time:.2f} seconds")
            print(f"🎯 Performance: {num_balls/test_time:.1f} balls/second")
        
        # Print scenario summary
        print(f"\n📈 {scenario_name} Results Summary:")
        for result in scenario_results:
            print(f"  {result['num_balls']} balls: {result['alive']}/{result['num_balls']} alive, {result['wall_bounces']} wall bounces, {result['ball_collisions']} ball collisions")
    
    # Print overall summary
    print(f"\n{'='*80}")
    print("OVERALL HIGH-DENSITY RESULTS SUMMARY")
    print(f"{'='*80}")
    
    for scenario_name, _, _ in scenarios:
        print(f"\n{scenario_name}:")
        scenario_data = [r for r in all_results if r['scenario'] == scenario_name]
        
        for result in scenario_data:
            print(f"  {result['num_balls']} balls: {result['alive']}/{result['num_balls']} alive, {result['wall_bounces']} wall bounces, {result['ball_collisions']} ball collisions")
    
    return all_results

if __name__ == "__main__":
    results = run_high_density_tests()
    
    # Final analysis
    print(f"\n🎯 FINAL HIGH-DENSITY ANALYSIS:")
    print(f"Total tests run: {len(results)}")
    
    # Check for any failures
    failures = [r for r in results if r['alive'] < r['num_balls']]
    if failures:
        print(f"⚠️  {len(failures)} tests had ball deaths")
        for failure in failures:
            print(f"  - {failure['scenario']} with {failure['num_balls']} balls: {failure['alive']}/{failure['num_balls']} balls alive")
    else:
        print(f"✅ All tests passed - all balls survived in all scenarios!")
    
    # Performance analysis
    print(f"\n🚀 PERFORMANCE ANALYSIS:")
    scenarios = [
        ("Wall Bounce Only", False, False),
        ("Wall Bounce + Ball Collision Bounce", True, True),
        ("Wall Bounce + Ball Collision Clip", True, False)
    ]
    for scenario_name, _, _ in scenarios:
        scenario_data = [r for r in results if r['scenario'] == scenario_name]
        print(f"\n{scenario_name}:")
        for result in scenario_data:
            balls_per_second = result['num_balls'] / result['test_time']
            print(f"  {result['num_balls']} balls: {balls_per_second:.1f} balls/second processing")
    
    print(f"\n🏁 High-density testing completed!")
