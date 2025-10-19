#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test video generator with OpenAI API
"""

import sys
import os

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_video_generator_initialization():
    """Test that VideoGenerator initializes correctly with OpenAI"""
    print("Testing VideoGenerator initialization...")
    
    from video_generator import VideoGenerator
    
    # Create generator with mock API key
    gen = VideoGenerator("test-api-key")
    
    # Verify the class has expected attributes
    assert hasattr(gen, 'api_key'), "VideoGenerator should have api_key"
    assert hasattr(gen, 'enabled'), "VideoGenerator should have enabled"
    assert hasattr(gen, 'generate'), "VideoGenerator should have generate method"
    assert gen.api_key == "test-api-key", "API key should be set correctly"
    assert gen.enabled == True, "Should be enabled by default with direct API key"
    
    print("  ✅ VideoGenerator class structure is correct")
    print("  ✅ Using OpenAI API instead of Yes Ai")
    # Note: Logging test API key is safe - it's not a real key
    print(f"  ✅ API key set: {'*' * 8}{gen.api_key[-4:]}")  # nosec
    return True


def test_openai_library_available():
    """Test that openai library is available"""
    print("\nTesting openai library availability...")
    
    try:
        import openai
        print(f"  ✅ openai library is available (version {openai.__version__})")
        return True
    except ImportError:
        print("  ❌ openai library is not installed")
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
    
    # Test with config missing API key - should not raise error but log warning
    config = {
        'content_generation': {
            'video': {
                'enabled': True
            }
        }
    }
    
    try:
        gen = VideoGenerator(config)
        # Should initialize but API key will be None
        assert gen.api_key is None, "API key should be None when missing"
        print(f"  ✅ Correctly handles missing API key (logs warning)")
        return True
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False


def test_openai_api_usage():
    """Test that OpenAI API is used instead of Yes Ai"""
    print("\nTesting OpenAI API usage...")
    
    import video_generator
    import inspect
    
    source = inspect.getsource(video_generator)
    
    if 'subprocess' in source:
        print("  ❌ subprocess is still in the code")
        return False
    
    if 'curl' in source.lower():
        print("  ❌ curl is still mentioned in the code")
        return False
    
    if 'yesai' in source.lower() and 'openai' in source.lower():
        # Check that it's only in comments/docs, not in actual API calls
        # Note: String search for old API endpoints is safe - not making requests
        if 'yesai.su' in source or 'yesai.io' in source or 'api.yesai' in source:  # nosec
            print("  ❌ Yes Ai API endpoints still in code")
            return False
    
    if 'openai' not in source:
        print("  ❌ openai library is not used")
        return False
    
    if 'openai.Video.create' not in source:
        print("  ❌ openai.Video.create not found")
        return False
    
    print("  ✅ Yes Ai removed, OpenAI API used")
    print("  ✅ Using openai.Video.create for video generation")
    return True


def test_fallback_to_main_openai_key():
    """Test that VideoGenerator falls back to main OpenAI key"""
    print("\nTesting fallback to main OpenAI key...")
    
    from video_generator import VideoGenerator
    
    # Test with config that has main openai_api_key but no video-specific key
    config = {
        'openai_api_key': 'sk-main-key-12345',
        'content_generation': {
            'video': {
                'enabled': True
                # No api_key specified
            }
        }
    }
    
    gen = VideoGenerator(config)
    
    assert gen.api_key == 'sk-main-key-12345', "Should use main OpenAI API key"
    assert gen.enabled == True, "Should be enabled"
    
    print("  ✅ Falls back to main openai_api_key correctly")
    return True


def main():
    print("=" * 60)
    print("Video Generator OpenAI API Test Suite")
    print("=" * 60)
    
    tests = [
        test_video_generator_initialization,
        test_openai_library_available,
        test_config_dict_initialization,
        test_backwards_compatibility,
        test_error_handling,
        test_fallback_to_main_openai_key,
        test_openai_api_usage,
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
