import time
import json as json_module
import requests
from logger import logger

class VideoGenerator:
    """
    Handles video generation via the Yes Ai API (Sora).
    Uses the requests library with browser-like headers to bypass security checks.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://yesai.su/v1"): # <--- ИЗМЕНЕНИЕ ЗДЕСЬ
        if not api_key:
            raise ValueError("Yes Ai API key is required for video generation")
        
        self.api_key = api_key
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

    def generate(self, prompt: str, duration: int = 5, resolution: str = "1080p"):
        """
        Generate a video from a text prompt.
        """
        response = None
        try:
            generation_url = f'{self.base_url}/video/generation'
            data = {
                "prompt": prompt,
                "duration": duration,
                "resolution": resolution,
                "model": "sora-1.0-turbo"
            }
            
            logger.info(f"🎬 Sending video generation request...")
            logger.info(f"  📝 Prompt: {prompt[:100]}...")
            
            response = requests.post(generation_url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            
            response_data = response.json()
            logger.info(f"  ✅ Response received: {response_data}")

            task_id = response_data.get('task_id')
            if not task_id:
                return {'error': 'No task_id in API response'}
            
            logger.info(f"✅ Task created: {task_id}")
            
            return self._poll_for_completion(task_id, duration, resolution)

        except requests.exceptions.HTTPError as e:
            error_msg = f"API request failed with status {e.response.status_code}. Response: {e.response.text[:200]}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}
        except requests.exceptions.JSONDecodeError:
            error_text = response.text if response else "No response object"
            error_msg = f"Failed to decode JSON. Server response: {error_text[:200]}"
            logger.error(f"❌ {error_msg}")
            return {'error': "API returned an invalid (non-JSON) response. See logs for details."}
        except requests.exceptions.RequestException as e:
            error_msg = f"API request error: {e}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}
        except Exception as e:
            logger.error(f"❌ Unexpected error in video generation: {e}", exc_info=True)
            return {'error': f'An unexpected error occurred: {str(e)}'}

    def _poll_for_completion(self, task_id: str, duration: int, resolution: str):
        status_url = f'{self.base_url}/video/status/{task_id}'
        max_attempts = 24 # 2 minutes
        
        for attempt in range(max_attempts):
            time.sleep(5)
            logger.info(f"⏳ Checking status... (attempt {attempt + 1}/{max_attempts})")
            
            response = None
            try:
                response = requests.get(status_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                status_data = response.json()
                
                status = status_data.get('status')
                if status == 'completed':
                    logger.info("✅ Generation completed!")
                    video_url = status_data.get('video_url')
                    if not video_url:
                        return {'error': 'Completed but no video_url in response'}
                    return {'video_url': video_url, 'duration': duration, 'resolution': resolution}
                
                elif status == 'failed':
                    error_msg = status_data.get('error', 'Generation failed without details')
                    return {'error': f"Generation failed: {error_msg}"}

            except requests.exceptions.JSONDecodeError:
                error_text = response.text if response else "No response object"
                logger.warning(f"⚠️ Failed to parse status JSON: {error_text[:200]}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Status check failed: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error during status check: {e}", exc_info=True)

        return {'error': 'Timeout: generation took too long'}
