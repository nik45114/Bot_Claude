#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test video generator with requests library
"""

import sys
import os

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_video_generator_initialization():
    """Test that VideoGenerator initializes correctly with requests"""
    print("Testing VideoGenerator initialization...")
    
    from video_generator import VideoGenerator
    
    # Create generator with mock API key
    gen = VideoGenerator("test-api-key")
    
    # Verify the class has expected attributes
    assert hasattr(gen, 'base_url'), "VideoGenerator should have base_url"
    assert hasattr(gen, 'api_key'), "VideoGenerator should have api_key"
    assert hasattr(gen, 'headers'), "VideoGenerator should have headers"
    assert hasattr(gen, 'generate'), "VideoGenerator should have generate method"
    assert "https://api.yesai.pro/api/v1" in gen.base_url, "base_url should use new endpoint"
    
    # Check headers are properly set
    assert 'Authorization' in gen.headers, "Headers should include Authorization"
    assert 'Content-Type' in gen.headers, "Headers should include Content-Type"
    assert 'Accept' in gen.headers, "Headers should include Accept"
    assert gen.headers['Content-Type'] == 'application/json', "Content-Type should be JSON"
    
    print("  ✅ VideoGenerator class structure is correct")
    print("  ✅ Using requests library instead of curl")
    print(f"  ✅ Base URL: {gen.base_url}")
    return True


def test_requests_library_available():
    """Test that requests library is available"""
    print("\nTesting requests library availability...")
    
    try:
        import requests
        print(f"  ✅ requests library is available (version {requests.__version__})")
        return True
    except ImportError:
        print("  ❌ requests library is not installed")
        return False


def test_config_dict_initialization():
    """Test that VideoGenerator accepts config dict"""
    print("\nTesting config dict initialization...")
    
    from video_generator import VideoGenerator
    
    # Test with config dict
    config = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'test-api-key-from-config'
            }
        }
    }
    
    gen = VideoGenerator(config)
    
    assert gen.api_key == 'test-api-key-from-config', "Should extract API key from config"
    assert gen.enabled == True, "Should extract enabled from config"
    
    print("  ✅ Config dict initialization works")
    return True


def test_backwards_compatibility():
    """Test that VideoGenerator still accepts direct API key string"""
    print("\nTesting backwards compatibility...")
    
    from video_generator import VideoGenerator
    
    # Test with direct API key string (old way)
    gen = VideoGenerator("test-api-key-direct")
    
    assert gen.api_key == 'test-api-key-direct', "Should accept direct API key"
    assert gen.enabled == True, "Should default enabled to True"
    
    print("  ✅ Backwards compatibility with direct API key works")
    return True


def test_error_handling():
    """Test error handling for missing API key"""
    print("\nTesting error handling...")
    
    from video_generator import VideoGenerator
    
    # Test with config missing API key
    config = {
        'content_generation': {
            'video': {
                'enabled': True
            }
        }
    }
    
    try:
        gen = VideoGenerator(config)
        print("  ❌ Should have raised ValueError for missing API key")
        return False
    except ValueError as e:
        print(f"  ✅ Correctly raised ValueError: {e}")
        return True


def test_no_curl_dependency():
    """Test that subprocess/curl is no longer used"""
    print("\nTesting removal of curl dependency...")
    
    import video_generator
    import inspect
    
    source = inspect.getsource(video_generator)
    
    if 'subprocess' in source:
        print("  ❌ subprocess is still in the code")
        return False
    
    if 'curl' in source.lower():
        print("  ❌ curl is still mentioned in the code")
        return False
    
    if 'requests' not in source:
        print("  ❌ requests library is not used")
        return False
    
    print("  ✅ curl/subprocess removed, requests library used")
    return True


def main():
    print("=" * 60)
    print("Video Generator Requests Library Test Suite")
    print("=" * 60)
    
    tests = [
        test_video_generator_initialization,
        test_requests_library_available,
        test_config_dict_initialization,
        test_backwards_compatibility,
        test_error_handling,
        test_no_curl_dependency,
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
