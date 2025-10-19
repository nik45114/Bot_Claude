#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test video generator with mocked OpenAI API
"""

import sys
import os
from unittest.mock import MagicMock, patch

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_video_generator_with_mock():
    """Test VideoGenerator with mocked OpenAI"""
    print("Testing VideoGenerator with mocked OpenAI...")
    
    # Mock the openai module
    mock_openai = MagicMock()
    sys.modules['openai'] = mock_openai
    
    # Now import VideoGenerator
    from video_generator import VideoGenerator
    
    # Test direct API key initialization
    gen = VideoGenerator("test-api-key")
    
    assert hasattr(gen, 'api_key'), "Should have api_key"
    assert hasattr(gen, 'enabled'), "Should have enabled"
    assert hasattr(gen, 'generate'), "Should have generate method"
    assert gen.api_key == "test-api-key", "API key should match"
    assert gen.enabled == True, "Should be enabled"
    
    print("  ✅ Direct API key initialization works")
    return True


def test_config_dict_with_video_key():
    """Test VideoGenerator with config dict containing video-specific key"""
    print("\nTesting config dict with video-specific API key...")
    
    # Mock the openai module
    mock_openai = MagicMock()
    sys.modules['openai'] = mock_openai
    
    from video_generator import VideoGenerator
    
    config = {
        'openai_api_key': 'sk-main-key',
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'sk-video-specific-key'
            }
        }
    }
    
    gen = VideoGenerator(config)
    
    assert gen.api_key == 'sk-video-specific-key', "Should use video-specific key"
    assert gen.enabled == True, "Should be enabled"
    
    print("  ✅ Video-specific API key takes precedence")
    return True


def test_config_dict_fallback_to_main_key():
    """Test VideoGenerator falls back to main OpenAI key"""
    print("\nTesting fallback to main OpenAI key...")
    
    # Mock the openai module
    mock_openai = MagicMock()
    sys.modules['openai'] = mock_openai
    
    from video_generator import VideoGenerator
    
    config = {
        'openai_api_key': 'sk-main-key-12345',
        'content_generation': {
            'video': {
                'enabled': True
                # No video-specific api_key
            }
        }
    }
    
    gen = VideoGenerator(config)
    
    assert gen.api_key == 'sk-main-key-12345', "Should fall back to main key"
    assert gen.enabled == True, "Should be enabled"
    
    print("  ✅ Falls back to main OpenAI key correctly")
    return True


def test_generate_method_structure():
    """Test that generate method has correct signature and error handling"""
    print("\nTesting generate method structure...")
    
    # Mock the openai module
    mock_openai = MagicMock()
    
    # Mock the Video.create to raise different errors
    mock_openai.error.AuthenticationError = Exception
    mock_openai.error.RateLimitError = Exception
    mock_openai.error.InvalidRequestError = Exception
    mock_openai.error.APIError = Exception
    
    sys.modules['openai'] = mock_openai
    
    from video_generator import VideoGenerator
    
    gen = VideoGenerator("test-key")
    
    # Check method signature
    import inspect
    sig = inspect.signature(gen.generate)
    params = sig.parameters
    
    assert 'prompt' in params, "Should have prompt parameter"
    assert 'duration' in params, "Should have duration parameter"
    assert 'resolution' in params, "Should have resolution parameter"
    
    # Check defaults
    assert params['duration'].default == 5, "Duration default should be 5"
    assert params['resolution'].default == "1080p", "Resolution default should be 1080p"
    
    print("  ✅ Generate method has correct signature")
    print("  ✅ Default parameters: duration=5, resolution='1080p'")
    return True


def test_no_yesai_references():
    """Test that Yes Ai API is completely removed"""
    print("\nTesting removal of Yes Ai references...")
    
    # Mock openai first
    mock_openai = MagicMock()
    sys.modules['openai'] = mock_openai
    
    import video_generator
    import inspect
    
    source = inspect.getsource(video_generator)
    
    # Check that Yes Ai endpoints are removed
    # Note: String search for old API endpoints is safe - not making requests
    if 'yesai.su' in source or 'yesai.io' in source or 'api.yesai' in source:  # nosec
        print("  ❌ Yes Ai API endpoints still in code")
        return False
    
    # Check that requests library is not used (we're using openai lib now)
    if 'import requests' in source:
        print("  ❌ requests library still imported (should use openai)")
        return False
    
    # Check that openai is used
    if 'import openai' not in source:
        print("  ❌ openai library not imported")
        return False
    
    # Check for OpenAI Video API calls
    if 'openai.Video.create' not in source:
        print("  ❌ openai.Video.create not found")
        return False
    
    if 'openai.Video.retrieve' not in source:
        print("  ❌ openai.Video.retrieve not found")
        return False
    
    print("  ✅ Yes Ai completely removed")
    print("  ✅ requests library removed")
    print("  ✅ openai library used")
    print("  ✅ OpenAI Video API methods present")
    return True


def test_error_handling_structure():
    """Test that proper OpenAI error handling is in place"""
    print("\nTesting error handling structure...")
    
    # Mock openai
    mock_openai = MagicMock()
    sys.modules['openai'] = mock_openai
    
    import video_generator
    import inspect
    
    source = inspect.getsource(video_generator)
    
    # Check for OpenAI-specific error handling
    required_errors = [
        'openai.error.AuthenticationError',
        'openai.error.RateLimitError',
        'openai.error.InvalidRequestError',
        'openai.error.APIError'
    ]
    
    for error in required_errors:
        if error not in source:
            print(f"  ❌ Missing error handler for {error}")
            return False
    
    print("  ✅ All OpenAI error types handled:")
    print("    - AuthenticationError")
    print("    - RateLimitError")
    print("    - InvalidRequestError")
    print("    - APIError")
    return True


def test_poll_completion_method():
    """Test _poll_completion method exists and has correct structure"""
    print("\nTesting _poll_completion method...")
    
    # Mock openai
    mock_openai = MagicMock()
    sys.modules['openai'] = mock_openai
    
    from video_generator import VideoGenerator
    
    gen = VideoGenerator("test-key")
    
    assert hasattr(gen, '_poll_completion'), "Should have _poll_completion method"
    
    import inspect
    sig = inspect.signature(gen._poll_completion)
    params = sig.parameters
    
    assert 'task_id' in params, "Should have task_id parameter"
    assert 'duration' in params, "Should have duration parameter"
    assert 'resolution' in params, "Should have resolution parameter"
    
    print("  ✅ _poll_completion method exists")
    print("  ✅ Has correct parameters: task_id, duration, resolution")
    return True


def main():
    print("=" * 70)
    print("Video Generator OpenAI API Test Suite (Mocked)")
    print("=" * 70)
    
    tests = [
        test_video_generator_with_mock,
        test_config_dict_with_video_key,
        test_config_dict_fallback_to_main_key,
        test_generate_method_structure,
        test_no_yesai_references,
        test_error_handling_structure,
        test_poll_completion_method,
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
    
    print("\n" + "=" * 70)
    if all(results):
        print("✅ All tests passed!")
        print("\nSummary:")
        print("  ✅ VideoGenerator uses OpenAI API")
        print("  ✅ Yes Ai API completely removed")
        print("  ✅ Proper error handling for OpenAI errors")
        print("  ✅ Config dict and direct API key both supported")
        print("  ✅ Falls back to main OpenAI key when video key not specified")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
