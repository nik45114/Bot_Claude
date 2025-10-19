#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Generator using OpenAI Sora API
Official OpenAI implementation - stable and reliable
"""

import logging
import time
from typing import Dict, Optional
import openai

logger = logging.getLogger(__name__)


class VideoGenerator:
    """Handles video generation via OpenAI Sora API"""
    
    def __init__(self, config_or_api_key):
        """
        Initialize VideoGenerator with OpenAI
        
        Args:
            config_or_api_key: Either a dict with video config or api_key string
        """
        if isinstance(config_or_api_key, dict):
            # New way: config dict
            video_config = config_or_api_key.get('content_generation', {}).get('video', {})
            self.enabled = video_config.get('enabled', False)
            self.api_key = video_config.get('api_key')
            
            # Fallback to main OpenAI key if video key not specified
            if not self.api_key:
                self.api_key = config_or_api_key.get('openai_api_key')
                logger.info("ℹ️ Using main OpenAI API key for video generation")
            
            if not self.api_key:
                logger.warning("⚠️ OpenAI API key not found in config")
        else:
            # Old way: direct api_key string
            self.api_key = config_or_api_key
            self.enabled = True
        
        # Set OpenAI API key (global pattern used throughout the bot)
        # Note: The bot uses a single OpenAI key for all services (GPT, DALL-E, Sora)
        # and VideoGenerator is instantiated only once, so this is safe
        openai.api_key = self.api_key
        
        logger.info("🎬 VideoGenerator initialized")
        logger.info("  - Provider: OpenAI Sora")
        logger.info("  - Model: sora-1.0-turbo")
    
    def generate(self, prompt: str, duration: int = 5, resolution: str = "1080p") -> Dict:
        """
        Generate video via OpenAI Sora API
        
        Args:
            prompt: Video description
            duration: Video duration in seconds (5 or 10)
            resolution: Video resolution (720p or 1080p)
            
        Returns:
            dict with 'video_url' or 'error'
        """
        try:
            logger.info(f"🎬 Generating video with OpenAI Sora")
            logger.info(f"  📝 Prompt: {prompt[:100]}...")
            logger.info(f"  ⏱️ Duration: {duration}s")
            logger.info(f"  📺 Resolution: {resolution}")
            
            # Map resolution to size parameter
            size_map = {
                "720p": "1280x720",
                "1080p": "1920x1080"
            }
            size = size_map.get(resolution, "1920x1080")
            
            # Determine model based on duration
            # sora-1.0-turbo: faster, cheaper (up to 5s)
            # sora-1.0: higher quality (up to 20s)
            model = "sora-1.0-turbo" if duration <= 5 else "sora-1.0"
            
            logger.info(f"  🤖 Using model: {model}")
            
            # Create video generation request
            response = openai.Video.create(
                model=model,
                prompt=prompt,
                size=size,
                duration=duration
            )
            
            logger.info(f"  ✅ Response received")
            
            # OpenAI Sora returns video URL directly or task ID for polling
            if hasattr(response, 'url'):
                # Direct URL (synchronous response)
                video_url = response.url
                logger.info(f"✅ Video generated successfully: {video_url}")
                return {
                    'video_url': video_url,
                    'duration': duration,
                    'resolution': resolution
                }
            elif hasattr(response, 'id'):
                # Task ID (asynchronous - need to poll)
                task_id = response.id
                logger.info(f"✅ Task created: {task_id}, polling for completion...")
                return self._poll_completion(task_id, duration, resolution)
            else:
                logger.error("❌ Unexpected response format")
                return {'error': 'Unexpected API response format'}
            
        except openai.error.AuthenticationError:
            logger.error("❌ OpenAI authentication failed - check API key")
            return {'error': 'Authentication failed. Check OpenAI API key.'}
        
        except openai.error.RateLimitError:
            logger.error("❌ OpenAI rate limit exceeded")
            return {'error': 'Rate limit exceeded. Try again later.'}
        
        except openai.error.InvalidRequestError as e:
            logger.error(f"❌ Invalid request: {e}")
            return {'error': f'Invalid request: {str(e)}'}
        
        except openai.error.APIError as e:
            logger.error(f"❌ OpenAI API error: {e}")
            return {'error': f'API error: {str(e)}'}
        
        except Exception as e:
            logger.error(f"❌ Video generation error: {e}")
            return {'error': str(e)}
    
    def _poll_completion(self, task_id: str, duration: int, resolution: str) -> Dict:
        """
        Poll for video generation completion
        
        Args:
            task_id: OpenAI task ID
            duration: Video duration
            resolution: Video resolution
            
        Returns:
            dict with 'video_url' or 'error'
        """
        max_attempts = 24  # 24 * 5 sec = 2 min
        
        for attempt in range(max_attempts):
            time.sleep(5)
            
            logger.info(f"⏳ Checking status... (attempt {attempt + 1}/{max_attempts})")
            
            try:
                # Retrieve task status
                response = openai.Video.retrieve(task_id)
                
                status = response.status
                logger.info(f"📊 Status: {status}")
                
                if status == 'completed':
                    video_url = response.url
                    logger.info(f"✅ Video generated successfully: {video_url}")
                    return {
                        'video_url': video_url,
                        'duration': duration,
                        'resolution': resolution
                    }
                elif status == 'failed':
                    error_msg = getattr(response, 'error', 'Generation failed')
                    logger.error(f"❌ Generation failed: {error_msg}")
                    return {'error': error_msg}
                
                # Status is 'processing' or 'queued' - continue polling
                
            except openai.error.APIError as e:
                logger.warning(f"⚠️ Status check failed: {e}")
                continue
            
            except Exception as e:
                logger.warning(f"⚠️ Status check error: {e}")
                continue
        
        logger.error("❌ Timeout: generation took too long")
        return {'error': 'Timeout: generation took too long'}
