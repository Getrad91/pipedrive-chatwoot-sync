#!/usr/bin/env python3
"""
Performance benchmark script to measure sync.py improvements
"""

import time
import json
import os
import sys
import subprocess
from datetime import datetime

def run_sync_with_timing():
    """Run sync.py and capture timing information"""
    print("🚀 Running performance benchmark...")
    print("=" * 50)
    
    start_time = time.time()
    
    try:
        result = subprocess.run([
            sys.executable, 
            os.path.join(os.path.dirname(__file__), 'app', 'sync.py')
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"⏱️  Total execution time: {duration:.2f} seconds")
        print(f"📅 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        if result.returncode == 0:
            print("✅ Sync completed successfully")
            
            output_lines = result.stdout.split('\n')
            performance_lines = [line for line in output_lines if '📊 Performance' in line]
            
            if performance_lines:
                print("\n📊 Performance Metrics:")
                for line in performance_lines:
                    print(f"  {line}")
            
            summary_lines = [line for line in output_lines if any(keyword in line for keyword in [
                'Total Customer organizations found',
                'Stored', 'organizations in database',
                'Sync completed:', 'synced,', 'errors',
                'Total sync duration',
                'Final memory usage',
                'Contact cache entries'
            ])]
            
            if summary_lines:
                print("\n📋 Summary:")
                for line in summary_lines:
                    print(f"  {line}")
                    
        else:
            print("❌ Sync failed")
            print(f"Return code: {result.returncode}")
            if result.stderr:
                print(f"Error output: {result.stderr}")
        
        benchmark_data = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'return_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
        benchmark_file = f"benchmark_results_{int(time.time())}.json"
        with open(benchmark_file, 'w') as f:
            json.dump(benchmark_data, f, indent=2)
        
        print(f"\n💾 Benchmark results saved to: {benchmark_file}")
        
        return duration, result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("⏰ Sync timed out after 5 minutes")
        return None, False
    except Exception as e:
        print(f"❌ Error running benchmark: {e}")
        return None, False

def compare_with_baseline(current_duration, baseline_file="baseline_performance.json"):
    """Compare current performance with baseline"""
    if not os.path.exists(baseline_file):
        print(f"📝 No baseline found. Creating baseline with current performance: {current_duration:.2f}s")
        baseline_data = {
            'duration_seconds': current_duration,
            'timestamp': datetime.now().isoformat(),
            'version': 'baseline'
        }
        with open(baseline_file, 'w') as f:
            json.dump(baseline_data, f, indent=2)
        return
    
    with open(baseline_file, 'r') as f:
        baseline_data = json.load(f)
    
    baseline_duration = baseline_data['duration_seconds']
    improvement = baseline_duration - current_duration
    improvement_percent = (improvement / baseline_duration) * 100
    
    print(f"\n📈 Performance Comparison:")
    print(f"  Baseline: {baseline_duration:.2f}s")
    print(f"  Current:  {current_duration:.2f}s")
    
    if improvement > 0:
        print(f"  🚀 Improvement: {improvement:.2f}s ({improvement_percent:.1f}% faster)")
    elif improvement < 0:
        print(f"  📉 Regression: {abs(improvement):.2f}s ({abs(improvement_percent):.1f}% slower)")
    else:
        print(f"  ➡️  No change in performance")

if __name__ == '__main__':
    print("🔬 Pipedrive-Chatwoot Sync Performance Benchmark")
    print("=" * 50)
    
    required_vars = ['PIPEDRIVE_API_KEY', 'CHATWOOT_API_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before running the benchmark.")
        sys.exit(1)
    
    duration, success = run_sync_with_timing()
    
    if success and duration is not None:
        compare_with_baseline(duration)
        print("\n✅ Benchmark completed successfully")
    else:
        print("\n❌ Benchmark failed")
        sys.exit(1)
