#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Generator using Yes Ai API
"""

import logging
import subprocess
import json as json_module
import time

logger = logging.getLogger(__name__)


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
    
    def generate(self, prompt: str, duration: int = 5, resolution: str = "1080p") -> dict:
        """
        Generate video via Yes Ai API using curl
        
        Args:
            prompt: Video description
            duration: Video duration in seconds (5 or 10)
            resolution: Video resolution (720p or 1080p)
            
        Returns:
            dict with 'video_url' or 'error'
        """
        try:
            # Step 1: Create generation request via curl
            data = {
                "prompt": prompt,
                "duration": duration,
                "resolution": resolution,
                "model": "sora-1.0-turbo"
            }
            
            logger.info(f"🎬 Sending video generation request via curl")
            logger.info(f"  📝 Prompt: {prompt[:100]}...")
            logger.info(f"  ⏱️ Duration: {duration}s")
            logger.info(f"  📺 Resolution: {resolution}")
            logger.info(f"  🤖 Model: sora-1.0-turbo")
            logger.info(f"  🌐 Endpoint: {self.base_url}/video/generation")
            
            curl_command = [
                'curl', '-k', '-X', 'POST',
                f'{self.base_url}/video/generation',
                '-H', f'Authorization: Bearer {self.api_key}',
                '-H', 'Content-Type: application/json',
                '-H', 'Accept: application/json',
                '-H', 'User-Agent: BotClaude/1.0 (+github.com/nik45114/Bot_Claude)',
                '-d', json_module.dumps(data),
                '--connect-timeout', '30',
                '--silent',
                '--show-error',
                '--fail',
                '--tlsv1.2'
            ]
            
            result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                error_detail = result.stderr.strip() or result.stdout.strip() or f'exit code {result.returncode}'
                error_msg = f'Curl error: {error_detail}'
                logger.error(f"❌ {error_msg}")
                return {'error': error_msg}
            
            try:
                response_data = json_module.loads(result.stdout)
            except json_module.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse response: {result.stdout[:200]}")
                return {'error': f'Invalid JSON response: {str(e)}'}
            
            logger.info(f"  ✅ Response received: {response_data}")
            
            task_id = response_data.get('task_id')
            
            if not task_id:
                logger.error("❌ No task_id in response")
                return {'error': 'No task_id in response'}
            
            logger.info(f"✅ Task created: {task_id}")
            
            # Step 2: Poll for completion (max 2 minutes)
            max_attempts = 24  # 24 * 5 sec = 2 min
            for attempt in range(max_attempts):
                time.sleep(5)
                
                logger.info(f"⏳ Checking status... (attempt {attempt + 1}/{max_attempts})")
                
                curl_status_command = [
                    'curl', '-k', '-X', 'GET',
                    f'{self.base_url}/video/status/{task_id}',
                    '-H', f'Authorization: Bearer {self.api_key}',
                    '-H', 'Accept: application/json',
                    '-H', 'User-Agent: BotClaude/1.0 (+github.com/nik45114/Bot_Claude)',
                    '--connect-timeout', '10',
                    '--silent',
                    '--show-error',
                    '--fail',
                    '--tlsv1.2'
                ]
                
                try:
                    status_result = subprocess.run(curl_status_command, capture_output=True, text=True, timeout=10)
                    
                    if status_result.returncode != 0:
                        error_detail = status_result.stderr.strip() or status_result.stdout.strip() or f'exit code {status_result.returncode}'
                        logger.warning(f"⚠️ Status check failed: {error_detail}")
                        continue
                    
                    status_data = json_module.loads(status_result.stdout)
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
                        
                except subprocess.TimeoutExpired:
                    logger.warning("⚠️ Status check timeout")
                    continue
                except json_module.JSONDecodeError:
                    logger.warning(f"⚠️ Invalid status response: {status_result.stdout[:100]}")
                    continue
                except Exception as e:
                    logger.warning(f"⚠️ Status check error: {e}")
                    continue
            
            logger.error("❌ Timeout: generation took too long")
            return {'error': 'Timeout: generation took too long'}
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Request timeout")
            return {'error': 'Request timeout'}
        except Exception as e:
            logger.error(f"❌ Video generation error: {e}")
            return {'error': str(e)}
