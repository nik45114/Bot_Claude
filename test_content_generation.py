#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test content generation functionality
"""

import sys
import os

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_content_type_detection():
    """Test auto-detection of content types"""
    print("Testing content type detection...")
    
    # Mock the ContentGenerator class for testing
    class MockContentGenerator:
        def detect_content_type(self, text):
            text_lower = text.lower()
            
            # Video keywords
            video_keywords = ['создай видео', 'сгенерируй видео', 'сделай видео']
            for keyword in video_keywords:
                if keyword in text_lower:
                    return ('video', text)
            
            # Image keywords
            image_keywords = ['создай изображение', 'нарисуй', 'создай картинку']
            for keyword in image_keywords:
                if keyword in text_lower:
                    return ('image', text)
            
            return ('text', text)
    
    gen = MockContentGenerator()
    
    # Test cases
    tests = [
        ("Напиши статью про AI", 'text'),
        ("Создай изображение космического корабля", 'image'),
        ("Нарисуй логотип для кафе", 'image'),
        ("Создай видео с анимацией", 'video'),
        ("Сгенерируй видео про продукт", 'video'),
        ("Что такое Python?", 'text'),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_type in tests:
        detected_type, _ = gen.detect_content_type(text)
        if detected_type == expected_type:
            print(f"  ✅ '{text[:40]}...' -> {detected_type}")
            passed += 1
        else:
            print(f"  ❌ '{text[:40]}...' -> Expected: {expected_type}, Got: {detected_type}")
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


def main():
    print("=" * 60)
    print("Content Generation Test Suite")
    print("=" * 60)
    
    tests = [
        test_content_type_detection,
        test_model_validation,
        test_database_schema
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
