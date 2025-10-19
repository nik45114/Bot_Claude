#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test that VideoGenerator uses browser-like headers
"""

import sys
import os

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_browser_headers():
    """Test that VideoGenerator uses browser-like headers to bypass security"""
    print("Testing browser-like headers...")
    
    from video_generator import VideoGenerator
    
    # Create generator with mock API key
    gen = VideoGenerator("test-api-key")
    
    # Check that all required headers are present
    required_headers = {
        'Authorization': 'Bearer test-api-key',
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Origin': 'https://www.yesai.pro',
        'Referer': 'https://www.yesai.pro/',
    }
    
    for header_name, expected_value in required_headers.items():
        assert header_name in gen.headers, f"Missing header: {header_name}"
        actual_value = gen.headers[header_name]
        assert actual_value == expected_value, f"Header {header_name}: expected '{expected_value}', got '{actual_value}'"
        print(f"  ✅ {header_name}: {actual_value}")
    
    # Verify User-Agent looks like a browser
    user_agent = gen.headers['User-Agent']
    assert 'Mozilla' in user_agent, "User-Agent should contain 'Mozilla'"
    assert 'Chrome' in user_agent, "User-Agent should contain 'Chrome'"
    assert 'Safari' in user_agent, "User-Agent should contain 'Safari'"
    print("  ✅ User-Agent mimics a real browser")
    
    # Verify Accept header includes multiple content types
    accept = gen.headers['Accept']
    assert 'application/json' in accept, "Accept should include 'application/json'"
    assert 'text/plain' in accept, "Accept should include 'text/plain'"
    assert '*/*' in accept, "Accept should include '*/*'"
    print("  ✅ Accept header includes multiple content types")
    
    # Verify Origin and Referer are set
    assert gen.headers['Origin'] == 'https://www.yesai.pro', "Origin should be https://www.yesai.pro"
    assert gen.headers['Referer'] == 'https://www.yesai.pro/', "Referer should be https://www.yesai.pro/"
    print("  ✅ Origin and Referer headers set correctly")
    
    return True


def main():
    print("=" * 60)
    print("Browser Headers Test for VideoGenerator")
    print("=" * 60)
    print()
    
    try:
        result = test_browser_headers()
        print()
        print("=" * 60)
        if result:
            print("✅ All browser header tests passed!")
            return 0
        else:
            print("❌ Tests failed")
            return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
