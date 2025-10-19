#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Generator using Yes Ai API
Uses the requests library for robust HTTP communication.
"""

import time
import json as json_module
import logging
import requests

logger = logging.getLogger(__name__)


class VideoGenerator:
    """
    Handles video generation via the Yes Ai API (Sora).
    Uses the requests library for robust HTTP communication.
    """
    
    def __init__(self, config_or_api_key, base_url: str = "https://api.yesai.pro/api/v1"):
        """
        Initialize VideoGenerator
        
        Args:
            config_or_api_key: Either a dict with video config or api_key string (for backwards compatibility)
            base_url: API base URL (default: https://api.yesai.pro/api/v1)
                     Note: Changed from https://api.yesai.io/v1 to use the correct endpoint
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
        
        if not self.api_key:
            raise ValueError("Yes Ai API key is required for video generation")
        
        self.base_url = base_url
        # Use headers that mimic a real web browser to bypass Cloudflare-like security
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
            'Origin': 'https://www.yesai.pro',
            'Referer': 'https://www.yesai.pro/',
        }
        
        logger.info("🎬 VideoGenerator initialized (using requests with browser headers)")
        logger.info(f"  - Provider: Yes Ai")
        logger.info(f"  - Endpoint: {self.base_url}")
    
    def generate(self, prompt: str, duration: int = 5, resolution: str = "1080p") -> dict:
        """
        Generate a video from a text prompt.
        
        Args:
            prompt: Video description
            duration: Video duration in seconds (5 or 10)
            resolution: Video resolution (720p or 1080p)
            
        Returns:
            dict with 'video_url' on success or 'error' on failure.
        """
        try:
            # Step 1: Create generation request
            generation_url = f'{self.base_url}/video/generation'
            data = {
                "prompt": prompt,
                "duration": duration,
                "resolution": resolution,
                "model": "sora-1.0-turbo"
            }
            
            logger.info(f"🎬 Sending video generation request via requests")
            logger.info(f"  📝 Prompt: {prompt[:100]}...")
            logger.info(f"  🌐 Endpoint: {generation_url}")
            
            response = requests.post(generation_url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            
            # Capture response text before parsing JSON to ensure it's available in exception handlers
            response_text = response.text
            response_data = response.json()
            logger.info(f"  ✅ Response received: {response_data}")

            task_id = response_data.get('task_id')
            if not task_id:
                logger.error("❌ No task_id in response")
                return {'error': 'No task_id in response'}
            
            logger.info(f"✅ Task created: {task_id}")
            
            # Step 2: Poll for completion (max 2 minutes)
            return self._poll_for_completion(task_id, duration, resolution)

        except requests.exceptions.HTTPError as e:
            error_msg = f"API request failed with status {e.response.status_code}: {e.response.text[:200]}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}
        except requests.exceptions.JSONDecodeError as e:
            error_msg = f"Failed to decode JSON response. Server response: {response_text[:200]}"
            logger.error(f"❌ {error_msg}")
            return {'error': "API returned an invalid (non-JSON) response. See logs for details."}
        except requests.exceptions.Timeout:
            logger.error("❌ Initial request timed out")
            return {'error': 'Timeout: initial request took too long'}
        except requests.exceptions.RequestException as e:
            error_msg = f"API request error: {e}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}
        except Exception as e:
            logger.error(f"❌ Unexpected error in video generation: {e}")
            return {'error': f'An unexpected error occurred: {str(e)}'}

    def _poll_for_completion(self, task_id: str, duration: int, resolution: str):
        """
        Poll the API for the video generation result.
        
        Args:
            task_id: The ID of the video generation task
            duration: Video duration in seconds (used for result metadata)
            resolution: Video resolution (used for result metadata)
            
        Returns:
            dict with 'video_url', 'duration', 'resolution' on success or 'error' on failure.
        """
        if not task_id:
            logger.error("❌ Invalid task_id provided to polling")
            return {'error': 'Invalid task_id'}
        
        status_url = f'{self.base_url}/video/status/{task_id}'
        max_attempts = 24  # 24 * 5 sec = 2 min
        
        for attempt in range(max_attempts):
            time.sleep(5)
            logger.info(f"⏳ Checking status... (attempt {attempt + 1}/{max_attempts})")
            
            try:
                response = requests.get(status_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                # Capture response text before parsing JSON to ensure it's available in exception handlers
                response_text = response.text
                status_data = response.json()
                
                if status_data.get('status') == 'completed':
                    logger.info("✅ Generation completed!")
                    video_url = status_data.get('video_url')
                    if not video_url:
                        logger.error("❌ Completed but no video_url found")
                        return {'error': 'Completed but no video_url'}
                    
                    return {
                        'video_url': video_url,
                        'duration': duration,
                        'resolution': resolution
                    }
                
                elif status_data.get('status') == 'failed':
                    error_msg = status_data.get('error', 'Generation failed without details')
                    logger.error(f"❌ Generation failed: {error_msg}")
                    return {'error': f"Generation failed: {error_msg}"}

            except requests.exceptions.JSONDecodeError:
                logger.warning(f"⚠️ Failed to parse status JSON: {response_text[:200]}")
            except requests.exceptions.Timeout:
                logger.warning("⚠️ Status check timed out")
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Status check failed: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error during status check: {e}")

        return {'error': 'Timeout: generation took too long'}
