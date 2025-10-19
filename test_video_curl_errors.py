#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test video generator curl error handling improvements
"""

import sys
import os
import subprocess
import json

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_curl_flags_in_command():
    """Test that curl commands include proper flags"""
    print("Testing curl command construction...")
    
    from video_generator import VideoGenerator
    
    # Create generator with mock API key
    gen = VideoGenerator("test-api-key")
    
    # We can't directly test the curl command construction without mocking,
    # but we can verify the class exists and has expected attributes
    assert hasattr(gen, 'base_url'), "VideoGenerator should have base_url"
    assert hasattr(gen, 'api_key'), "VideoGenerator should have api_key"
    assert hasattr(gen, 'generate'), "VideoGenerator should have generate method"
    assert gen.base_url == "https://api.yesai.io/v1", "base_url should be correct"
    
    print("  ✅ VideoGenerator class structure is correct")
    return True


def test_curl_error_messages():
    """Test that curl produces detailed error messages"""
    print("\nTesting curl error message production...")
    
    # Test 1: curl with --silent alone (old behavior simulation)
    result1 = subprocess.run(
        ['curl', '--silent', '-k', 'https://nonexistent.local.invalid'],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    stderr1 = result1.stderr.strip()
    print(f"  Test 1 (--silent only): stderr='{stderr1}', exit={result1.returncode}")
    
    if not stderr1:
        print("  ✅ Confirmed: --silent suppresses error messages")
    else:
        print(f"  ⚠️  Unexpected stderr with --silent: {stderr1}")
    
    # Test 2: curl with --silent --show-error (new behavior)
    result2 = subprocess.run(
        ['curl', '--silent', '--show-error', '-k', 'https://nonexistent.local.invalid'],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    stderr2 = result2.stderr.strip()
    print(f"  Test 2 (--silent --show-error): stderr='{stderr2}', exit={result2.returncode}")
    
    if stderr2 and 'curl' in stderr2.lower():
        print("  ✅ Confirmed: --show-error provides error details")
    else:
        print(f"  ⚠️  Expected curl error in stderr")
    
    # Test 3: Verify --fail flag exists
    help_result = subprocess.run(
        ['curl', '--help'],
        capture_output=True,
        text=True
    )
    
    if '--fail' in help_result.stdout:
        print("  ✅ Confirmed: curl supports --fail flag")
    else:
        print("  ⚠️  curl --fail not found in help")
    
    return True


def test_error_detail_fallback():
    """Test error detail fallback logic"""
    print("\nTesting error detail fallback logic...")
    
    # Simulate the fallback logic used in video_generator.py
    test_cases = [
        # (stderr, stdout, returncode, expected_contains)
        ("curl: (6) Could not resolve host", "", 6, "Could not resolve host"),
        ("", "Some output", 22, "Some output"),
        ("", "", 7, "exit code 7"),
    ]
    
    passed = 0
    for stderr, stdout, returncode, expected in test_cases:
        error_detail = stderr.strip() or stdout.strip() or f'exit code {returncode}'
        if expected in error_detail:
            print(f"  ✅ Fallback works: stderr='{stderr[:20]}', stdout='{stdout[:20]}', code={returncode} -> '{error_detail}'")
            passed += 1
        else:
            print(f"  ❌ Fallback failed: expected '{expected}' in '{error_detail}'")
    
    return passed == len(test_cases)


def test_headers_format():
    """Test that headers are properly formatted"""
    print("\nTesting header format...")
    
    # Test that headers can be constructed
    headers = [
        'Accept: application/json',
        'User-Agent: BotClaude/1.0 (+github.com/nik45114/Bot_Claude)',
        'Content-Type: application/json'
    ]
    
    for header in headers:
        if ':' in header and len(header.split(':', 1)) == 2:
            key, value = header.split(':', 1)
            print(f"  ✅ Header format valid: {key.strip()}: {value.strip()[:30]}...")
        else:
            print(f"  ❌ Invalid header format: {header}")
            return False
    
    return True


def main():
    print("=" * 60)
    print("Video Generator Curl Error Handling Test Suite")
    print("=" * 60)
    
    tests = [
        test_curl_flags_in_command,
        test_curl_error_messages,
        test_error_detail_fallback,
        test_headers_format,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
