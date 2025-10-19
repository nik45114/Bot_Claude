# Yes Ai Video Generation Setup Guide

## Overview

This bot now supports video generation via **Yes Ai** (Sora API). Users can generate short videos from text descriptions using the `/video` command.

## Configuration

### 1. API Key Setup

The Yes Ai API key is configured in `config.json`:

```json
{
  "content_generation": {
    "video": {
      "enabled": true,
      "provider": "yesai",
      "api_key": "yes-06b045099e782bd35a48c69699e8d77a6a23f69983a02d06caacceb8aaa4",
      "duration": 5,
      "resolution": "1080p"
    }
  }
}
```

**Security Note**: 
- The `config.json` file is gitignored by default
- Never commit your API key to version control
- The key shown above is a placeholder - use your own key

### 2. Configuration Options

- **enabled** (boolean): Enable/disable video generation
- **provider** (string): Video generation provider (currently "yesai")
- **api_key** (string): Your Yes Ai API key (format: `yes-xxxxxx...`)
- **base_url** (string): Base URL for the API (default: "https://api.yesai.io/v1")
- **duration** (integer): Default video duration in seconds (5 or 10)
- **resolution** (string): Default video resolution ("720p" or "1080p")
- **network** (object): Network tuning options for reliability

#### Network Configuration

The `network` section provides advanced options to handle network and TLS issues:

```json
{
  "content_generation": {
    "video": {
      "enabled": true,
      "provider": "yesai",
      "api_key": "yes-xxxxxx...",
      "base_url": "https://api.yesai.io/v1",
      "duration": 5,
      "resolution": "1080p",
      "network": {
        "bypass_proxy": false,
        "force_http1_1": false,
        "force_tlsv1_2": false,
        "ipv4_only": false,
        "retries": 2,
        "retry_backoff_sec": 2,
        "base_url_candidates": []
      }
    }
  }
}
```

Network Options:
- **bypass_proxy** (boolean): Bypass system proxy settings (adds `--noproxy '*'`)
- **force_http1_1** (boolean): Force HTTP/1.1 protocol (adds `--http1.1`)
- **force_tlsv1_2** (boolean): Force TLS 1.2 (adds `--tlsv1.2`)
- **ipv4_only** (boolean): Use IPv4 only (adds `--ipv4`)
- **retries** (integer): Number of retry attempts (default: 2)
- **retry_backoff_sec** (integer): Base backoff in seconds between retries (default: 2, exponential)
- **base_url_candidates** (array): Alternative base URLs to try if primary fails

## Usage

### Basic Command

```
/video <description>
```

### Examples

```
/video кот играет с мячиком
/video дракон летит над горами
/video закат на океане
/video футуристический город
```

### Generation Time

- Typical generation time: **30-90 seconds**
- The bot will show a "Генерирую видео..." message while processing
- Status is checked every 5 seconds
- Maximum wait time: 2 minutes (then timeout error)

## Cost Information

**Important**: Video generation costs credits/tokens from your Yes Ai account.

Approximate costs (check Yes Ai pricing for current rates):
- 5 second video at 1080p: ~X credits
- 10 second video at 1080p: ~Y credits

**Recommendation**: Monitor your API usage on the Yes Ai dashboard.

## Limitations and Guidelines

### Content Restrictions

Yes Ai API has the following restrictions:
- ❌ **No 18+ content** - Adult, violent, or explicit content is prohibited
- ❌ **No deepfakes** - Cannot create videos of real people without consent
- ❌ **No harmful content** - Violence, hate speech, illegal activities
- ❌ **No copyrighted material** - Cannot recreate copyrighted characters/brands

### Technical Limitations

- **Duration**: Maximum 10 seconds per video
- **Resolution**: Up to 1080p
- **Queue time**: May be longer during peak hours
- **Timeout**: Generation that takes >2 minutes will timeout

## Error Handling

### Common Errors

1. **"API error: 401"**
   - Invalid or expired API key
   - Solution: Check your API key in config.json

2. **"API error: 429"**
   - Rate limit exceeded
   - Solution: Wait a few minutes before trying again

3. **"Timeout: generation took too long"**
   - Generation exceeded 2 minutes
   - Solution: Try a simpler prompt or try again later

4. **"Generation failed"**
   - Content policy violation or technical error
   - Solution: Review prompt for policy violations, try again

5. **"No task_id in response"**
   - API communication error
   - Solution: Check internet connection, try again

6. **"curl: (35) error:0A000458:SSL routines::tlsv1 unrecognized name"**
   - TLS/SNI error due to network configuration
   - Solution: See [TLS/SNI Errors](#tlssni-errors-curl-35-error0a000458ssl-routinestlsv1-unrecognized-name) section above

## Troubleshooting

### TLS/SNI Errors (curl: (35) error:0A000458:SSL routines::tlsv1 unrecognized name)

Some network environments (proxies, accelerators, certain ISPs) may encounter TLS Server Name Indication (SNI) errors when connecting to the Yes Ai API. This manifests as:

```
curl: (35) error:0A000458:SSL routines::tlsv1 unrecognized name
```

**Solution**: Enable network resilience options in your config.json:

```json
{
  "content_generation": {
    "video": {
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

The bot will:
1. Automatically detect TLS errors and retry with enforced network options
2. Log fallback attempts for debugging
3. Try alternative base URLs if configured in `base_url_candidates`

**Alternative Base URLs**: If you have access to an alternative endpoint or proxy:

```json
{
  "content_generation": {
    "video": {
      "base_url": "https://api.yesai.io/v1",
      "network": {
        "base_url_candidates": [
          "https://backup-api.example.com/v1",
          "https://api-proxy.example.com/yesai/v1"
        ]
      }
    }
  }
}
```

### Video generation is disabled

**Error message**: "❌ Генерация видео отключена в конфигурации"

**Solution**:
1. Check `config.json` has `content_generation.video.enabled: true`
2. Verify API key is present in config
3. Restart the bot

### Generation takes too long

**If generations consistently timeout**:
1. Try simpler prompts
2. Check Yes Ai status page for outages
3. Reduce resolution from 1080p to 720p in config
4. Reduce duration from 10s to 5s in config

### API key validation

The bot validates API key format on startup. Valid format:
```
yes-[alphanumeric string]
```

If the key is invalid, you'll see an error in the logs.

## Monitoring

### Database Logging

All video generation requests are logged to the `content_generations` table:

```sql
SELECT * FROM content_generations WHERE content_type = 'video' ORDER BY created_at DESC LIMIT 10;
```

Fields logged:
- `user_id`: Who requested the video
- `request_text`: The prompt used
- `video_url`: Final video URL (if successful)
- `status`: 'completed', 'failed', or 'processing'
- `error_message`: Error details (if failed)
- `created_at` / `completed_at`: Timestamps

### Log Messages

The bot logs detailed information:
```
🎬 Sending video generation request for: <prompt>
✅ Task created: <task_id>
⏳ Checking status... (attempt X/24)
📊 Status: <status>
✅ Video generated successfully: <url>
```

Check logs with:
```bash
tail -f <bot-log-file>
```

## Best Practices

1. **Descriptive Prompts**: Be specific about what you want
   - Good: "кот играет с красным мячиком на зелёном газоне"
   - Bad: "кот"

2. **Manage Expectations**: Set realistic expectations with users
   - Videos are short (5-10 seconds)
   - Generation takes time (30-90 seconds)
   - Not all prompts will work perfectly

3. **Monitor Usage**: Keep track of API costs
   - Set up usage alerts in Yes Ai dashboard
   - Consider implementing user rate limits

4. **Test Prompts**: Test various prompts to understand quality
   - Some types of content work better than others
   - Iterate on prompts for best results

## API Key Security

### Protecting Your Key

1. **Never commit** `config.json` to git (it's gitignored)
2. **Use environment variables** in production:
   ```python
   api_key = os.getenv('YESAI_API_KEY') or config.get('content_generation', {}).get('video', {}).get('api_key')
   ```
3. **Rotate keys regularly** if exposed
4. **Limit permissions** in Yes Ai dashboard if possible

### Key Rotation

If your key is compromised:
1. Generate new key in Yes Ai dashboard
2. Update `config.json` with new key
3. Restart the bot
4. Revoke the old key

## Support

### Yes Ai Support
- Website: https://yesai.io
- Documentation: https://docs.yesai.io
- Support: support@yesai.io

### Bot Issues
- If video generation fails consistently, check bot logs
- Report issues to bot maintainer
- Include error messages and timestamps

## Future Enhancements

Potential improvements:
- [ ] Custom duration per request
- [ ] Custom resolution per request
- [ ] Video style/model selection
- [ ] Batch generation
- [ ] Generation history per user
- [ ] Admin-only restriction option
- [ ] Cost tracking per user
- [ ] Generation queue management
