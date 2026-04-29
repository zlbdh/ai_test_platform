"""Test batch runner module"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.batch_runner import BatchRunner, TestCase

async def _executor(tc: TestCase):
    return {'ok': True, 'id': tc.id}

def main():
    cases = [
        TestCase(id='t1', instruction='Test 1'),
        TestCase(id='t2', instruction='Test 2'),
        TestCase(id='t3', instruction='Test 3')
    ]
    
    runner = BatchRunner(max_concurrency=2)
    result = asyncio.run(runner.run_batch(cases, _executor))
    
    print("=== Batch Result ===")
    print(f"Status: {result.status}")
    print(f"Total: {result.total}")
    print(f"Success: {result.success}")
    print(f"Success Rate: {result.success_rate:.1f}%")
    print("=== OK ===")

if __name__ == "__main__":
    main()
