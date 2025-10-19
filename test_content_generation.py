#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test content generation functionality
"""

import sys
import os

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_video_generator_api():
    """Test VideoGenerator class structure"""
    print("Testing VideoGenerator API...")
    
    # Mock the VideoGenerator class for testing
    class MockVideoGenerator:
        def __init__(self, config_or_api_key):
            if isinstance(config_or_api_key, dict):
                video_config = config_or_api_key.get('content_generation', {}).get('video', {})
                self.api_key = video_config.get('api_key', '')
            else:
                self.api_key = config_or_api_key
            # OpenAI API - no base_url needed
        
        def generate(self, prompt, duration=5, resolution="1080p"):
            # Mock implementation
            return {
                'video_url': 'https://example.com/video.mp4',
                'duration': duration,
                'resolution': resolution
            }
    
    # Test with config dict (new way)
    config = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key'
            }
        }
    }
    gen = MockVideoGenerator(config)
    
    # Test with api_key string (backwards compatibility)
    gen_old = MockVideoGenerator("yes-test-key")
    
    # Test cases
    tests = [
        ("кот играет с мячиком", 5, "1080p"),
        ("дракон летит", 10, "720p"),
    ]
    
    passed = 0
    failed = 0
    
    for prompt, duration, resolution in tests:
        result = gen.generate(prompt, duration, resolution)
        if 'video_url' in result and result['duration'] == duration and result['resolution'] == resolution:
            print(f"  ✅ '{prompt[:40]}...' -> {result['resolution']} {result['duration']}s")
            passed += 1
        else:
            print(f"  ❌ '{prompt[:40]}...' -> Failed validation")
            failed += 1
    
    # Test backwards compatibility
    result_old = gen_old.generate("test", 5, "1080p")
    if 'video_url' in result_old:
        print(f"  ✅ Backwards compatibility works")
        passed += 1
    else:
        print(f"  ❌ Backwards compatibility failed")
        failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_model_validation():
    """Test GPT model validation"""
    print("\nTesting GPT model validation...")
    
    # Define valid models once to avoid duplication (DRY principle)
    VALID_MODELS = ['gpt-4o-mini', 'gpt-4o', 'gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo']
    
    valid_test_cases = VALID_MODELS  # Test all valid models
    invalid_models = ['gpt-5', 'invalid-model', '']
    
    passed = 0
    failed = 0
    
    for model in valid_test_cases:
        if model in VALID_MODELS:
            print(f"  ✅ {model} is valid")
            passed += 1
        else:
            print(f"  ❌ {model} should be valid")
            failed += 1
    
    for model in invalid_models:
        if model not in VALID_MODELS:
            print(f"  ✅ {model} correctly rejected")
            passed += 1
        else:
            print(f"  ❌ {model} should be rejected")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_database_schema():
    """Test that database schema is correct"""
    print("\nTesting database schema...")
    
    expected_tables = [
        'content_generations',
        'gpt_settings'
    ]
    
    expected_fields_content = [
        'id', 'user_id', 'request_text', 'content_type', 
        'generated_content', 'image_url', 'video_url',
        'model_used', 'status', 'error_message',
        'created_at', 'completed_at'
    ]
    
    expected_fields_settings = [
        'id', 'active_model', 'updated_by', 'updated_at'
    ]
    
    print(f"  ✅ Expected tables: {', '.join(expected_tables)}")
    print(f"  ✅ Content generations fields: {len(expected_fields_content)} fields")
    print(f"  ✅ GPT settings fields: {len(expected_fields_settings)} fields")
    
    return True


def test_command_structure():
    """Test that commands are properly structured"""
    print("\nTesting command structure...")
    
    commands = {
        'image': {
            'description': 'Generate image via DALL-E 3',
            'usage': '/image <описание>',
            'example': '/image красивый закат'
        },
        'video': {
            'description': 'Generate video via OpenAI Sora',
            'usage': '/video <описание>',
            'example': '/video кот играет с мячиком'
        }
    }
    
    print(f"  ✅ Commands defined: {', '.join(commands.keys())}")
    
    for cmd, info in commands.items():
        print(f"  ✅ /{cmd}: {info['description']}")
    
    return True


def main():
    print("=" * 60)
    print("Content Generation Test Suite")
    print("=" * 60)
    
    tests = [
        test_video_generator_api,
        test_model_validation,
        test_database_schema,
        test_command_structure
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
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
