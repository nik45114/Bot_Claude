#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Generator using Yes Ai API
"""

import logging
import requests
import time
import urllib3
import ssl
from urllib3.util.ssl_ import create_urllib3_context
from requests.adapters import HTTPAdapter

# Disable SSL warnings when verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class SSLContextAdapter(HTTPAdapter):
    """Custom adapter to disable hostname verification and SNI"""
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


class VideoGenerator:
    def __init__(self, config_or_api_key):
        """
        Initialize VideoGenerator
        
        Args:
            config_or_api_key: Either a dict with video config or api_key string (for backwards compatibility)
        """
        if isinstance(config_or_api_key, dict):
            # New way: config dict
            video_config = config_or_api_key.get('content_generation', {}).get('video', {})
            self.enabled = video_config.get('enabled', False)
            self.api_key = video_config.get('api_key', None)
            if not self.api_key:
                logger.warning("⚠️ Video API key not found in config")
        else:
            # Old way: direct api_key string (backwards compatibility)
            self.api_key = config_or_api_key
            self.enabled = True
        
        self.base_url = "https://api.yesai.io/v1"
        
        # Create session with custom SSL adapter
        self.session = requests.Session()
        self.session.mount('https://', SSLContextAdapter())
    
    def generate(self, prompt: str, duration: int = 5, resolution: str = "1080p") -> dict:
        """
        Generate video via Yes Ai API
        
        Args:
            prompt: Video description
            duration: Video duration in seconds (5 or 10)
            resolution: Video resolution (720p or 1080p)
            
        Returns:
            dict with 'video_url' or 'error'
        """
        try:
            # Step 1: Create generation request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "prompt": prompt,
                "duration": duration,
                "resolution": resolution,
                "model": "sora-1.0-turbo"
            }
            
            logger.info(f"🎬 Sending video generation request")
            logger.info(f"  📝 Prompt: {prompt[:100]}...")
            logger.info(f"  ⏱️ Duration: {duration}s")
            logger.info(f"  📺 Resolution: {resolution}")
            logger.info(f"  🤖 Model: sora-1.0-turbo")
            logger.info(f"  🌐 Endpoint: {self.base_url}/video/generation")
            
            response = self.session.post(
                f"{self.base_url}/video/generation",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code != 200:
                error_msg = f'API error: {response.status_code}'
                logger.error(f"❌ {error_msg}")
                try:
                    error_detail = response.json()
                    logger.error(f"  📄 Response: {error_detail}")
                except (ValueError, requests.exceptions.JSONDecodeError) as e:
                    logger.error(f"  📄 Response text: {response.text[:200]}")
                    logger.debug(f"  Failed to parse JSON: {e}")
                return {'error': error_msg}
            
            result = response.json()
            logger.info(f"  ✅ Response received: {result}")
            task_id = result.get('task_id')
            
            if not task_id:
                logger.error("❌ No task_id in response")
                return {'error': 'No task_id in response'}
            
            logger.info(f"✅ Task created: {task_id}")
            
            # Step 2: Poll for completion (max 2 minutes)
            max_attempts = 24  # 24 * 5 sec = 2 min
            for attempt in range(max_attempts):
                time.sleep(5)  # Wait 5 seconds between checks
                
                logger.info(f"⏳ Checking status... (attempt {attempt + 1}/{max_attempts})")
                
                status_response = self.session.get(
                    f"{self.base_url}/video/status/{task_id}",
                    headers=headers,
                    timeout=10
                )
                
                if status_response.status_code != 200:
                    logger.warning(f"⚠️ Status check failed: {status_response.status_code}")
                    try:
                        logger.warning(f"  📄 Response: {status_response.json()}")
                    except (ValueError, requests.exceptions.JSONDecodeError) as e:
                        logger.warning(f"  📄 Response text: {status_response.text[:200]}")
                        logger.debug(f"  Failed to parse JSON: {e}")
                    continue
                
                status_data = status_response.json()
                status = status_data.get('status')
                
                logger.info(f"📊 Status: {status}")
                logger.debug(f"  📄 Full response: {status_data}")
                
                if status == 'completed':
                    video_url = status_data.get('video_url')
                    logger.info(f"✅ Video generated successfully: {video_url}")
                    return {
                        'video_url': video_url,
                        'duration': duration,
                        'resolution': resolution
                    }
                elif status == 'failed':
                    error_msg = status_data.get('error', 'Generation failed')
                    logger.error(f"❌ Generation failed: {error_msg}")
                    return {'error': error_msg}
            
            logger.error("❌ Timeout: generation took too long")
            return {'error': 'Timeout: generation took too long'}
            
        except requests.exceptions.Timeout:
            logger.error("❌ Request timeout")
            return {'error': 'Request timeout'}
        except Exception as e:
            logger.error(f"❌ Video generation error: {e}")
            return {'error': str(e)}
