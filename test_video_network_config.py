#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test video generator network configuration and retry logic
"""

import sys
import os
import json

# Add the directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_network_config_loading():
    """Test that network config is loaded correctly"""
    print("Testing network config loading...")
    
    from video_generator import VideoGenerator
    
    # Test 1: Default config (backwards compatibility)
    gen_old = VideoGenerator("test-api-key")
    assert gen_old.base_url == "https://api.yesai.io/v1", "Default base_url should be set"
    assert gen_old.bypass_proxy == False, "Default bypass_proxy should be False"
    assert gen_old.force_http1_1 == False, "Default force_http1_1 should be False"
    assert gen_old.force_tlsv1_2 == False, "Default force_tlsv1_2 should be False"
    assert gen_old.ipv4_only == False, "Default ipv4_only should be False"
    assert gen_old.retries == 2, "Default retries should be 2"
    assert gen_old.retry_backoff_sec == 2, "Default retry_backoff_sec should be 2"
    assert gen_old.base_url_candidates == [], "Default base_url_candidates should be empty"
    print("  ✅ Backwards compatibility defaults correct")
    
    # Test 2: Config with network options
    config = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key',
                'base_url': 'https://custom-api.example.com/v1',
                'network': {
                    'bypass_proxy': True,
                    'force_http1_1': True,
                    'force_tlsv1_2': True,
                    'ipv4_only': True,
                    'retries': 3,
                    'retry_backoff_sec': 5,
                    'base_url_candidates': ['https://backup.example.com/v1']
                }
            }
        }
    }
    gen_new = VideoGenerator(config)
    assert gen_new.base_url == "https://custom-api.example.com/v1", "Custom base_url should be loaded"
    assert gen_new.bypass_proxy == True, "bypass_proxy should be loaded"
    assert gen_new.force_http1_1 == True, "force_http1_1 should be loaded"
    assert gen_new.force_tlsv1_2 == True, "force_tlsv1_2 should be loaded"
    assert gen_new.ipv4_only == True, "ipv4_only should be loaded"
    assert gen_new.retries == 3, "retries should be loaded"
    assert gen_new.retry_backoff_sec == 5, "retry_backoff_sec should be loaded"
    assert len(gen_new.base_url_candidates) == 1, "base_url_candidates should be loaded"
    print("  ✅ Custom network config loaded correctly")
    
    # Test 3: Partial network config (should use defaults for missing values)
    config_partial = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key',
                'network': {
                    'bypass_proxy': True
                }
            }
        }
    }
    gen_partial = VideoGenerator(config_partial)
    assert gen_partial.bypass_proxy == True, "Specified value should be loaded"
    assert gen_partial.force_http1_1 == False, "Unspecified value should default to False"
    assert gen_partial.retries == 2, "Unspecified value should default to 2"
    print("  ✅ Partial config with defaults works correctly")
    
    return True


def test_build_curl_flags():
    """Test curl flags construction"""
    print("\nTesting curl flags construction...")
    
    from video_generator import VideoGenerator
    
    # Test 1: No network options
    config_none = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key'
            }
        }
    }
    gen_none = VideoGenerator(config_none)
    flags = gen_none._build_curl_flags()
    assert len(flags) == 0, "No flags should be added when options are disabled"
    print("  ✅ No flags when options disabled")
    
    # Test 2: All network options enabled
    config_all = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key',
                'network': {
                    'bypass_proxy': True,
                    'force_http1_1': True,
                    'force_tlsv1_2': True,
                    'ipv4_only': True
                }
            }
        }
    }
    gen_all = VideoGenerator(config_all)
    flags = gen_all._build_curl_flags()
    assert '--noproxy' in flags, "Should include --noproxy"
    assert '*' in flags, "Should include '*' for noproxy"
    assert '--http1.1' in flags, "Should include --http1.1"
    assert '--tlsv1.2' in flags, "Should include --tlsv1.2"
    assert '--ipv4' in flags, "Should include --ipv4"
    print("  ✅ All flags added when all options enabled")
    
    # Test 3: Enforce network options (fallback mode)
    config_enforce = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key',
                'network': {
                    'bypass_proxy': False,
                    'force_http1_1': False,
                    'force_tlsv1_2': False
                }
            }
        }
    }
    gen_enforce = VideoGenerator(config_enforce)
    flags_enforced = gen_enforce._build_curl_flags(enforce_network_options=True)
    assert '--noproxy' in flags_enforced, "Should include --noproxy when enforced"
    assert '--http1.1' in flags_enforced, "Should include --http1.1 when enforced"
    assert '--tlsv1.2' in flags_enforced, "Should include --tlsv1.2 when enforced"
    print("  ✅ Enforcement works correctly for fallback mode")
    
    # Test 4: Selective options
    config_selective = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key',
                'network': {
                    'bypass_proxy': True,
                    'force_http1_1': False,
                    'force_tlsv1_2': True,
                    'ipv4_only': False
                }
            }
        }
    }
    gen_selective = VideoGenerator(config_selective)
    flags_selective = gen_selective._build_curl_flags()
    assert '--noproxy' in flags_selective, "Should include enabled option"
    assert '--tlsv1.2' in flags_selective, "Should include enabled option"
    assert '--http1.1' not in flags_selective, "Should not include disabled option"
    assert '--ipv4' not in flags_selective, "Should not include disabled option"
    print("  ✅ Selective options work correctly")
    
    return True


def test_config_json_example():
    """Test that config.json.example is valid JSON and has expected structure"""
    print("\nTesting config.json.example validity...")
    
    config_path = os.path.join(os.path.dirname(__file__), 'config.json.example')
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print("  ✅ config.json.example is valid JSON")
    except json.JSONDecodeError as e:
        print(f"  ❌ config.json.example has invalid JSON: {e}")
        return False
    
    # Check structure
    assert 'content_generation' in config, "Should have content_generation section"
    assert 'video' in config['content_generation'], "Should have video section"
    
    video_config = config['content_generation']['video']
    assert 'base_url' in video_config, "Should have base_url field"
    assert 'network' in video_config, "Should have network section"
    
    network_config = video_config['network']
    expected_fields = [
        'bypass_proxy', 'force_http1_1', 'force_tlsv1_2', 
        'ipv4_only', 'retries', 'retry_backoff_sec', 'base_url_candidates'
    ]
    
    for field in expected_fields:
        assert field in network_config, f"Should have {field} in network config"
    
    print(f"  ✅ All expected fields present in network config")
    
    # Check types
    assert isinstance(network_config['bypass_proxy'], bool), "bypass_proxy should be boolean"
    assert isinstance(network_config['retries'], int), "retries should be integer"
    assert isinstance(network_config['base_url_candidates'], list), "base_url_candidates should be array"
    print("  ✅ Field types are correct")
    
    return True


def test_base_url_customization():
    """Test that custom base_url is used correctly"""
    print("\nTesting base_url customization...")
    
    from video_generator import VideoGenerator
    
    # Test custom base_url
    config = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key',
                'base_url': 'https://my-custom-proxy.example.com/api/v1'
            }
        }
    }
    gen = VideoGenerator(config)
    assert gen.base_url == 'https://my-custom-proxy.example.com/api/v1', "Custom base_url should be set"
    print("  ✅ Custom base_url is loaded")
    
    # Test base_url_candidates
    config_candidates = {
        'content_generation': {
            'video': {
                'enabled': True,
                'api_key': 'yes-test-key',
                'base_url': 'https://primary.example.com/v1',
                'network': {
                    'base_url_candidates': [
                        'https://backup1.example.com/v1',
                        'https://backup2.example.com/v1'
                    ]
                }
            }
        }
    }
    gen_candidates = VideoGenerator(config_candidates)
    assert len(gen_candidates.base_url_candidates) == 2, "Should have 2 candidate URLs"
    assert gen_candidates.base_url_candidates[0] == 'https://backup1.example.com/v1', "First candidate should match"
    print("  ✅ base_url_candidates are loaded correctly")
    
    return True


def main():
    print("=" * 60)
    print("Video Generator Network Configuration Test Suite")
    print("=" * 60)
    
    tests = [
        test_network_config_loading,
        test_build_curl_flags,
        test_config_json_example,
        test_base_url_customization,
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
