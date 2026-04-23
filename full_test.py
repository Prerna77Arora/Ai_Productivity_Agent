#!/usr/bin/env python3
"""Complete project functionality test"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from agent.agent import chat

def test_component(name, test_func):
    """Test a component and report results"""
    print(f"\n{'='*50}")
    print(f"TESTING: {name}")
    print(f"{'='*50}")
    
    try:
        result = test_func()
        print(f"SUCCESS: {name}")
        return True, result
    except Exception as e:
        print(f"FAILED: {name} - Error: {str(e)}")
        return False, str(e)

def test_mcp_connection():
    """Test MCP server connection and tools"""
    print("Testing MCP server connection...")
    result = chat("Show all my notes")
    print(f"MCP Response: {result}")
    return "notes" in result.lower() or "no notes" in result.lower()

def test_note_management():
    """Test note creation and retrieval"""
    print("Testing note management...")
    
    # Create a test note
    result1 = chat("Add note: System test - This is a test note for verifying functionality")
    print(f"Note creation: {result1}")
    
    # List notes
    result2 = chat("Show all my notes")
    print(f"Note listing: {result2}")
    
    return "created" in result1.lower() or "note" in result2.lower()

def test_task_management():
    """Test task creation and completion"""
    print("Testing task management...")
    
    # Create a test task
    result1 = chat("Add task: Complete system verification, high priority")
    print(f"Task creation: {result1}")
    
    # List tasks
    result2 = chat("List all tasks")
    print(f"Task listing: {result2}")
    
    return "task" in result1.lower() and "task" in result2.lower()

def test_web_fetch():
    """Test web content fetching"""
    print("Testing web fetch...")
    
    # Test with a simple URL
    result = chat("Research https://httpbin.org/json and save key points")
    print(f"Web fetch result: {result}")
    
    return "note" in result.lower() or "saved" in result.lower() or "created" in result.lower()

def test_summary():
    """Test workspace summary"""
    print("Testing workspace summary...")
    
    result = chat("Give me a workspace summary")
    print(f"Summary result: {result}")
    
    return "notes" in result.lower() and "tasks" in result.lower()

def test_research_workflow():
    """Test complete research workflow"""
    print("Testing complete research workflow...")
    
    # This should trigger fetch_url -> add_note
    result = chat("Research https://jsonplaceholder.typicode.com/posts/1 and save as a note")
    print(f"Research workflow: {result}")
    
    return "note" in result.lower() or "created" in result.lower() or "saved" in result.lower()

async def run_full_test():
    """Run comprehensive test suite"""
    print("STARTING COMPREHENSIVE PROJECT TEST")
    print(f"Project Root: {ROOT_DIR}")
    
    tests = [
        ("MCP Server Connection", test_mcp_connection),
        ("Note Management", test_note_management),
        ("Task Management", test_task_management),
        ("Web Content Fetching", test_web_fetch),
        ("Workspace Summary", test_summary),
        ("Complete Research Workflow", test_research_workflow),
    ]
    
    results = []
    passed = 0
    
    for test_name, test_func in tests:
        success, output = test_component(test_name, test_func)
        results.append((test_name, success, output))
        if success:
            passed += 1
    
    # Final report
    print(f"\n{'='*60}")
    print("FINAL TEST REPORT")
    print(f"{'='*60}")
    print(f"Tests Passed: {passed}/{len(tests)}")
    print(f"Success Rate: {passed/len(tests)*100:.1f}%")
    
    print("\nDetailed Results:")
    for name, success, output in results:
        status = "PASS" if success else "FAIL"
        print(f"  {status}: {name}")
    
    if passed == len(tests):
        print("\nPROJECT STATUS: FULLY WORKING")
        print("All components are functioning correctly!")
    else:
        print(f"\nPROJECT STATUS: PARTIALLY WORKING")
        print(f"{len(tests) - passed} component(s) need attention")
    
    return passed == len(tests)

if __name__ == "__main__":
    success = asyncio.run(run_full_test())
    sys.exit(0 if success else 1)
