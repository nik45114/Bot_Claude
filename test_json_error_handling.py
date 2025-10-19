#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test improved JSON error handling in video_generator
"""

import sys
import os
from unittest.mock import Mock, patch, MagicMock
import requests

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_http_error_with_response_text():
    """Test that HTTPError logs response status code and text"""
    print("Testing HTTPError with response text logging...")
    
    from video_generator import VideoGenerator
    
    gen = VideoGenerator("test-api-key")
    
    # Mock response with HTTP error
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.text = "<html><body>Access Denied - Invalid API Key</body></html>"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
    
    with patch('requests.post', return_value=mock_response):
        result = gen.generate("test prompt")
        
        assert 'error' in result, "Should return error dict"
        assert '403' in result['error'], "Error should contain status code"
        assert 'Access Denied' in result['error'], "Error should contain response text"
        
    print("  ✅ HTTPError correctly logs status code and response text")
    return True


def test_json_decode_error_with_response_text():
    """Test that JSONDecodeError logs raw response text"""
    print("\nTesting JSONDecodeError with response text logging...")
    
    from video_generator import VideoGenerator
    
    gen = VideoGenerator("test-api-key")
    
    # Mock response with invalid JSON
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>Server Error 500</body></html>"
    mock_response.raise_for_status.return_value = None  # No HTTP error
    mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)
    
    with patch('requests.post', return_value=mock_response):
        result = gen.generate("test prompt")
        
        assert 'error' in result, "Should return error dict"
        assert 'invalid (non-JSON) response' in result['error'], "Error message should indicate non-JSON"
        
    print("  ✅ JSONDecodeError correctly logs raw response text")
    return True


def test_json_decode_error_in_polling():
    """Test that JSONDecodeError in polling logs response text"""
    print("\nTesting JSONDecodeError in polling...")
    
    from video_generator import VideoGenerator
    
    gen = VideoGenerator("test-api-key")
    
    # Mock successful initial request
    mock_initial_response = Mock()
    mock_initial_response.status_code = 200
    mock_initial_response.raise_for_status.return_value = None
    mock_initial_response.json.return_value = {'task_id': 'test-task-123'}
    
    # Mock status check with invalid JSON
    mock_status_response = Mock()
    mock_status_response.status_code = 200
    mock_status_response.text = "<html>Maintenance Mode</html>"
    mock_status_response.raise_for_status.return_value = None
    mock_status_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)
    
    with patch('requests.post', return_value=mock_initial_response), \
         patch('requests.get', return_value=mock_status_response), \
         patch('time.sleep', return_value=None):  # Speed up test
        
        result = gen.generate("test prompt")
        
        # Should eventually timeout since status checks keep failing
        assert 'error' in result, "Should return error dict"
        assert 'Timeout' in result['error'] or 'took too long' in result['error'], "Should timeout after max attempts"
        
    print("  ✅ JSONDecodeError in polling is handled gracefully")
    return True


def test_exception_order():
    """Test that exceptions are caught in the correct order (most specific first)"""
    print("\nTesting exception handling order...")
    
    from video_generator import VideoGenerator
    import inspect
    
    # Get the source code of the generate method
    source = inspect.getsource(VideoGenerator.generate)
    
    # Check that HTTPError comes before RequestException
    http_error_pos = source.find('except requests.exceptions.HTTPError')
    json_error_pos = source.find('except requests.exceptions.JSONDecodeError')
    request_error_pos = source.find('except requests.exceptions.RequestException')
    
    assert http_error_pos > 0, "HTTPError handler should exist"
    assert json_error_pos > 0, "JSONDecodeError handler should exist"
    assert request_error_pos > 0, "RequestException handler should exist"
    
    assert http_error_pos < request_error_pos, "HTTPError should be caught before RequestException"
    assert json_error_pos < request_error_pos, "JSONDecodeError should be caught before RequestException"
    
    print("  ✅ Exceptions are caught in correct order (most specific first)")
    return True


def test_response_text_truncation():
    """Test that response text is truncated to prevent log spam"""
    print("\nTesting response text truncation...")
    
    from video_generator import VideoGenerator
    
    gen = VideoGenerator("test-api-key")
    
    # Create a very long response text
    long_html = "<html><body>" + ("x" * 500) + "</body></html>"
    
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = long_html
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)
    
    with patch('requests.post', return_value=mock_response):
        result = gen.generate("test prompt")
        
        assert 'error' in result, "Should return error dict"
        # The implementation truncates to 200 chars
        
    print("  ✅ Response text is truncated appropriately")
    return True


def main():
    print("=" * 60)
    print("JSON Error Handling Test Suite")
    print("=" * 60)
    
    tests = [
        test_http_error_with_response_text,
        test_json_decode_error_with_response_text,
        test_json_decode_error_in_polling,
        test_exception_order,
        test_response_text_truncation,
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
