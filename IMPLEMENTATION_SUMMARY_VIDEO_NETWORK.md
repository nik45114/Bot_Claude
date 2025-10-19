# Video Generator Network Configuration Enhancement - Implementation Summary

## Overview

Enhanced the video generator to handle TLS/SNI errors and provide configurable network options for improved reliability in diverse network environments.

## Problem Addressed

Some environments encounter TLS errors when calling YesAi API:
```
curl: (35) error:0A000458:SSL routines::tlsv1 unrecognized name
```

This is a server-side TLS/SNI alert that can occur with certain network paths, accelerators, or proxies.

## Solution

### 1. Configurable Base URL
- Added `base_url` field to config.json (defaults to `https://api.yesai.io/v1`)
- Supports custom endpoints without code changes

### 2. Network Tuning Options
Added `network` configuration section with the following options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `bypass_proxy` | boolean | false | Bypass system proxy (adds `--noproxy '*'`) |
| `force_http1_1` | boolean | false | Force HTTP/1.1 protocol (adds `--http1.1`) |
| `force_tlsv1_2` | boolean | false | Force TLS 1.2 (adds `--tlsv1.2`) |
| `ipv4_only` | boolean | false | Use IPv4 only (adds `--ipv4`) |
| `retries` | integer | 2 | Number of retry attempts |
| `retry_backoff_sec` | integer | 2 | Base backoff in seconds (exponential) |
| `base_url_candidates` | array | [] | Alternative base URLs to try on failure |

### 3. Retry/Fallback Strategy

#### Exponential Backoff
- Retry 1: Wait 2 seconds (2 * 2^0)
- Retry 2: Wait 4 seconds (2 * 2^1)
- Retry 3: Wait 8 seconds (2 * 2^2)
- etc.

#### Automatic TLS Error Detection
When detecting TLS/SNI errors (curl exit code 35 or "unrecognized name" in stderr):
1. Logs the error: `⚠️ TLS/SNI error detected: ...`
2. Immediately retries with enforced network options
3. Logs fallback: `🔄 Retrying immediately with enforced network options...`
4. Does not count against retry limit for this immediate retry

#### Base URL Fallback
If primary base_url fails after all retries, automatically tries:
1. Each URL in `base_url_candidates` array
2. Logs switch: `🔄 Switching to alternate base_url: ...`
3. Returns first successful result

### 4. Applied to Both Operations
- Video generation request
- Status polling (same network options and retry logic)

## Configuration Examples

### Minimal (Backwards Compatible)
```json
{
  "content_generation": {
    "video": {
      "enabled": true,
      "api_key": "yes-xxxxxx..."
    }
  }
}
```

### TLS Error Resilience
```json
{
  "content_generation": {
    "video": {
      "enabled": true,
      "api_key": "yes-xxxxxx...",
      "network": {
        "bypass_proxy": true,
        "force_http1_1": true,
        "force_tlsv1_2": true,
        "retries": 3
      }
    }
  }
}
```

### Multiple Fallback URLs
```json
{
  "content_generation": {
    "video": {
      "enabled": true,
      "api_key": "yes-xxxxxx...",
      "base_url": "https://api.yesai.io/v1",
      "network": {
        "bypass_proxy": true,
        "force_http1_1": true,
        "force_tlsv1_2": true,
        "base_url_candidates": [
          "https://backup-api.example.com/v1",
          "https://api-proxy.example.com/yesai/v1"
        ]
      }
    }
  }
}
```

## Code Changes

### video_generator.py
- **Lines 31-42**: Read network configuration from config
- **Lines 44-55**: Set defaults for backwards compatibility
- **Lines 57-82**: `_build_curl_flags()` method to construct curl flags based on config
- **Lines 84-168**: `_execute_curl_with_retry()` method with:
  - Exponential backoff
  - TLS error detection
  - Automatic enforcement fallback
  - Proper retry counting
- **Lines 180-299**: Updated `generate()` method to:
  - Iterate through base_url_candidates
  - Use retry logic for both generation and status polling
  - Log URL switches

### config.json.example
- Added complete `network` section with all options

### YESAI_SETUP.md
- Documented all new configuration fields
- Added TLS/SNI troubleshooting section
- Added to common errors list

### CONTENT_GENERATION_GUIDE.md
- Added network configuration example
- Added TLS troubleshooting section

## Testing

### test_video_network_config.py (New)
- Tests network config loading (backwards compatibility, full config, partial config)
- Tests curl flags construction (none, all, enforced, selective)
- Tests config.json.example validity
- Tests base_url customization and candidates

### Existing Tests (All Pass)
- test_video_curl_errors.py
- test_content_generation.py

## Acceptance Criteria Met

✅ Default behavior unchanged for healthy environments  
✅ TLS errors trigger automatic retry with enforced network options  
✅ Fallback logged for debugging  
✅ base_url and base_url_candidates configurable without code changes  
✅ Status polling uses same network options and retry policy  
✅ Backwards compatible with existing configurations  
✅ All tests pass  
✅ Documentation updated with troubleshooting guidance  

## Security Considerations

- Still using `-k` flag to avoid CA bundle issues (as before)
- No changes to authentication mechanism
- Network options only affect curl transport, not API security

## Future Enhancements

Potential improvements:
- [ ] Metrics for retry success/failure rates
- [ ] Configuration validation with warnings
- [ ] Per-endpoint timeout configuration
- [ ] Circuit breaker pattern for persistently failing endpoints
