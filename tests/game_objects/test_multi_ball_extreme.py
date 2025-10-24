#!/usr/bin/env python3
"""Extreme multi-ball test with maximum balls."""

import time
from test_multi_ball_base import MultiBallTestBase

def run_extreme_tests():
    """Run multi-ball tests with extreme ball density."""
    print("=== EXTREME MULTI-BALL TESTS ===")
    print("Testing with maximum balls to stress test the system to its limits...")
    
    # Extreme test configurations
    test_configs = [
        # (num_balls, fps, duration_seconds, test_name)
        (500, 60, 20, "500 balls @ 60 FPS for 20 seconds"),
        (1000, 60, 20, "1000 balls @ 60 FPS for 20 seconds"),
        (2000, 60, 20, "2000 balls @ 60 FPS for 20 seconds"),
        (5000, 60, 20, "5000 balls @ 60 FPS for 20 seconds"),
    ]
    
    # Test scenarios - focusing on the most intensive ones
    scenarios = [
        ("Wall Bounce + Ball Collision Bounce", True, True),
        ("Wall Bounce + Ball Collision Clip", True, False)
    ]
    
    all_results = []
    
    for scenario_name, enable_collisions, enable_bouncing in scenarios:
        print(f"\n{'='*100}")
        print(f"SCENARIO: {scenario_name}")
        print(f"{'='*100}")
        
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
            print(f"🔥 Collision rate: {ball_collisions/test_time:.1f} collisions/second")
        
        # Print scenario summary
        print(f"\n📈 {scenario_name} Results Summary:")
        for result in scenario_results:
            print(f"  {result['num_balls']} balls: {result['alive']}/{result['num_balls']} alive, {result['wall_bounces']} wall bounces, {result['ball_collisions']} ball collisions")
    
    # Print overall summary
    print(f"\n{'='*100}")
    print("OVERALL EXTREME RESULTS SUMMARY")
    print(f"{'='*100}")
    
    for scenario_name, _, _ in scenarios:
        print(f"\n{scenario_name}:")
        scenario_data = [r for r in all_results if r['scenario'] == scenario_name]
        
        for result in scenario_data:
            print(f"  {result['num_balls']} balls: {result['alive']}/{result['num_balls']} alive, {result['wall_bounces']} wall bounces, {result['ball_collisions']} ball collisions")
    
    return all_results

if __name__ == "__main__":
    results = run_extreme_tests()
    
    # Final analysis
    print(f"\n🎯 FINAL EXTREME ANALYSIS:")
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
        ("Wall Bounce + Ball Collision Bounce", True, True),
        ("Wall Bounce + Ball Collision Clip", True, False)
    ]
    for scenario_name, _, _ in scenarios:
        scenario_data = [r for r in results if r['scenario'] == scenario_name]
        print(f"\n{scenario_name}:")
        for result in scenario_data:
            balls_per_second = result['num_balls'] / result['test_time']
            collisions_per_second = result['ball_collisions'] / result['test_time']
            print(f"  {result['num_balls']} balls: {balls_per_second:.1f} balls/second, {collisions_per_second:.1f} collisions/second")
    
    print(f"\n🏁 Extreme testing completed!")
