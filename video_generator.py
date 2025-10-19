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
            
            # Read base_url from config or use default
            self.base_url = video_config.get('base_url', "https://api.yesai.io/v1")
            
            # Read network options
            network_config = video_config.get('network', {})
            self.bypass_proxy = network_config.get('bypass_proxy', False)
            self.force_http1_1 = network_config.get('force_http1_1', False)
            self.force_tlsv1_2 = network_config.get('force_tlsv1_2', False)
            self.ipv4_only = network_config.get('ipv4_only', False)
            self.retries = network_config.get('retries', 2)
            self.retry_backoff_sec = network_config.get('retry_backoff_sec', 2)
            self.base_url_candidates = network_config.get('base_url_candidates', [])
        else:
            # Old way: direct api_key string (backwards compatibility)
            self.api_key = config_or_api_key
            self.enabled = True
            self.base_url = "https://api.yesai.io/v1"
            # Default network settings for backwards compatibility
            self.bypass_proxy = False
            self.force_http1_1 = False
            self.force_tlsv1_2 = False
            self.ipv4_only = False
            self.retries = 2
            self.retry_backoff_sec = 2
            self.base_url_candidates = []
    
    def _build_curl_flags(self, enforce_network_options=False):
        """
        Build curl flags based on network configuration
        
        Args:
            enforce_network_options: If True, force network options even if not configured
            
        Returns:
            List of curl flags to add to command
        """
        flags = []
        
        # Add network tuning options
        if self.bypass_proxy or enforce_network_options:
            flags.extend(['--noproxy', '*'])
        
        if self.force_http1_1 or enforce_network_options:
            flags.append('--http1.1')
        
        if self.force_tlsv1_2 or enforce_network_options:
            flags.append('--tlsv1.2')
        
        if self.ipv4_only:
            flags.append('--ipv4')
        
        return flags
    
    def _execute_curl_with_retry(self, curl_command, operation_name, enforce_fallback=False):
        """
        Execute curl command with retry logic
        
        Args:
            curl_command: Base curl command without network flags
            operation_name: Name of operation for logging
            enforce_fallback: If True, enforce network options on first try
            
        Returns:
            Tuple of (success: bool, response_data: dict or None, error_msg: str or None)
        """
        for attempt in range(self.retries + 1):
            if attempt > 0:
                backoff = self.retry_backoff_sec * (2 ** (attempt - 1))  # Exponential backoff
                logger.info(f"⏳ Retry {attempt}/{self.retries} after {backoff}s backoff...")
                time.sleep(backoff)
            
            # Build command with network flags
            # Enforce network options on retry or if requested
            enforce_options = enforce_fallback or attempt > 0
            network_flags = self._build_curl_flags(enforce_network_options=enforce_options)
            
            # Insert network flags after curl but before -X
            full_command = curl_command[:1] + network_flags + curl_command[1:]
            
            try:
                result = subprocess.run(full_command, capture_output=True, text=True, timeout=30)
                
                # Check for errors
                if result.returncode != 0:
                    error_detail = result.stderr.strip() or result.stdout.strip() or f'exit code {result.returncode}'
                    
                    # Check for specific TLS/SSL errors that should trigger fallback
                    if 'unrecognized name' in error_detail.lower() or result.returncode == 35:
                        logger.warning(f"⚠️ TLS/SNI error detected: {error_detail}")
                        if not enforce_fallback and attempt == 0:
                            logger.info(f"🔄 Retrying with enforced network options...")
                            enforce_fallback = True
                            # Continue to next retry immediately
                            continue
                    
                    logger.warning(f"⚠️ {operation_name} attempt {attempt + 1} failed: {error_detail}")
                    
                    # If this was the last retry, return error
                    if attempt == self.retries:
                        return False, None, f'Curl error: {error_detail}'
                    
                    continue
                
                # Try to parse JSON response
                try:
                    response_data = json_module.loads(result.stdout)
                    return True, response_data, None
                except json_module.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON parse error on attempt {attempt + 1}: {str(e)}")
                    
                    # If this was the last retry, return error
                    if attempt == self.retries:
                        return False, None, f'Invalid JSON response: {str(e)}'
                    
                    continue
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"⚠️ {operation_name} timeout on attempt {attempt + 1}")
                
                # If this was the last retry, return error
                if attempt == self.retries:
                    return False, None, 'Request timeout'
                
                continue
            except Exception as e:
                logger.warning(f"⚠️ {operation_name} error on attempt {attempt + 1}: {e}")
                
                # If this was the last retry, return error
                if attempt == self.retries:
                    return False, None, str(e)
                
                continue
        
        # Should not reach here, but just in case
        return False, None, 'Max retries exceeded'
    
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
        # Build list of base URLs to try
        urls_to_try = [self.base_url] + self.base_url_candidates
        
        for url_index, base_url in enumerate(urls_to_try):
            if url_index > 0:
                logger.info(f"🔄 Switching to alternate base_url: {base_url}")
            
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
                logger.info(f"  🌐 Endpoint: {base_url}/video/generation")
                
                curl_command = [
                    'curl', '-k', '-X', 'POST',
                    f'{base_url}/video/generation',
                    '-H', f'Authorization: Bearer {self.api_key}',
                    '-H', 'Content-Type: application/json',
                    '-H', 'Accept: application/json',
                    '-H', 'User-Agent: BotClaude/1.0 (+github.com/nik45114/Bot_Claude)',
                    '-d', json_module.dumps(data),
                    '--connect-timeout', '30',
                    '--silent',
                    '--show-error',
                    '--fail'
                ]
                
                # Execute with retry logic
                success, response_data, error_msg = self._execute_curl_with_retry(
                    curl_command, 
                    "Generation request"
                )
                
                if not success:
                    logger.error(f"❌ {error_msg}")
                    # Try next URL if available
                    if url_index < len(urls_to_try) - 1:
                        continue
                    return {'error': error_msg}
                
                logger.info(f"  ✅ Response received: {response_data}")
                
                task_id = response_data.get('task_id')
                
                if not task_id:
                    logger.error("❌ No task_id in response")
                    # Try next URL if available
                    if url_index < len(urls_to_try) - 1:
                        continue
                    return {'error': 'No task_id in response'}
                
                logger.info(f"✅ Task created: {task_id}")
                
                # Step 2: Poll for completion (max 2 minutes)
                max_attempts = 24  # 24 * 5 sec = 2 min
                for attempt in range(max_attempts):
                    time.sleep(5)
                    
                    logger.info(f"⏳ Checking status... (attempt {attempt + 1}/{max_attempts})")
                    
                    curl_status_command = [
                        'curl', '-k', '-X', 'GET',
                        f'{base_url}/video/status/{task_id}',
                        '-H', f'Authorization: Bearer {self.api_key}',
                        '-H', 'Accept: application/json',
                        '-H', 'User-Agent: BotClaude/1.0 (+github.com/nik45114/Bot_Claude)',
                        '--connect-timeout', '10',
                        '--silent',
                        '--show-error',
                        '--fail'
                    ]
                    
                    # Execute status check with retry logic
                    success, status_data, error_msg = self._execute_curl_with_retry(
                        curl_status_command,
                        "Status check"
                    )
                    
                    if not success:
                        logger.warning(f"⚠️ Status check failed: {error_msg}")
                        continue
                    
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
                
            except Exception as e:
                logger.error(f"❌ Video generation error: {e}")
                # Try next URL if available
                if url_index < len(urls_to_try) - 1:
                    continue
                return {'error': str(e)}
        
        # If we exhausted all URLs
        return {'error': 'All base URLs failed'}
