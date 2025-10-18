#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Generator using Yes Ai API
"""

import logging
import requests
import time

logger = logging.getLogger(__name__)


class VideoGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.yesai.io/v1"
    
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
                "resolution": resolution
            }
            
            logger.info(f"🎬 Sending video generation request for: {prompt[:50]}...")
            
            response = requests.post(
                f"{self.base_url}/sora/generate",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code != 200:
                error_msg = f'API error: {response.status_code}'
                logger.error(f"❌ {error_msg}")
                return {'error': error_msg}
            
            result = response.json()
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
                
                status_response = requests.get(
                    f"{self.base_url}/sora/status/{task_id}",
                    headers=headers,
                    timeout=10
                )
                
                if status_response.status_code != 200:
                    logger.warning(f"⚠️ Status check failed: {status_response.status_code}")
                    continue
                
                status_data = status_response.json()
                status = status_data.get('status')
                
                logger.info(f"📊 Status: {status}")
                
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
