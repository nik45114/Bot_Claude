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
    assert 'Authorization' in gen.headers, "Missing Authorization header"
    assert gen.headers['Authorization'] == 'Bearer test-api-key', "Authorization header incorrect"
    print(f"  ✅ Authorization: Bearer ***")
    
    assert 'Content-Type' in gen.headers, "Missing Content-Type header"
    assert gen.headers['Content-Type'] == 'application/json', "Content-Type should be application/json"
    print("  ✅ Content-Type: application/json")
    
    assert 'Accept' in gen.headers, "Missing Accept header"
    accept_header = gen.headers['Accept']
    assert 'application/json' in accept_header, "Accept should include application/json"
    assert 'text/plain' in accept_header, "Accept should include text/plain"
    print(f"  ✅ Accept: {accept_header}")
    
    assert 'User-Agent' in gen.headers, "Missing User-Agent header"
    user_agent = gen.headers['User-Agent']
    print(f"  ✅ User-Agent: {user_agent}")
    
    assert 'Origin' in gen.headers, "Missing Origin header"
    origin_header = gen.headers['Origin']
    assert origin_header == 'https://www.yesai.pro', "Origin should be https://www.yesai.pro"
    print(f"  ✅ Origin: {origin_header}")
    
    assert 'Referer' in gen.headers, "Missing Referer header"
    referer_header = gen.headers['Referer']
    assert referer_header == 'https://www.yesai.pro/', "Referer should be https://www.yesai.pro/"
    print(f"  ✅ Referer: {referer_header}")
    
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
