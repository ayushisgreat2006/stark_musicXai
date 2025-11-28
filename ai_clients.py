import aiohttp
import json
import asyncio
from datetime import datetime
import re
from config import *

# Groq Client
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"❌ Failed to initialize Groq: {e}")

# GeminiGen API
def parse_netscape_cookies(content: str) -> dict:
    cookies = {}
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '\t' in line:
            try:
                parts = line.split('\t', 6)
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value
            except:
                continue
    return cookies

class GeminiGenAPI:
    def __init__(self, cookies: dict, bearer_token: str):
        self.cookies = cookies
        self.bearer_token = bearer_token
        self.base_url = "https://api.geminigen.ai"
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        }
    
    async def generate_video(self, prompt: str) -> str:
        async with aiohttp.ClientSession(cookies=self.cookies, headers=self.headers) as session:
            form = aiohttp.FormData()
            form.add_field('prompt', prompt)
            form.add_field('model', 'veo-3-fast')
            form.add_field('duration', '8')
            
            async with session.post(f"{self.base_url}/api/video-gen/veo", data=form) as resp:
                if resp.status not in (200, 202):
                    raise Exception(f"Generation failed: HTTP {resp.status}")
                result = await resp.json()
                return result.get("uuid") or result.get("id")
    
    async def poll_for_video(self, job_id: str, timeout: int = 300) -> str:
        async with aiohttp.ClientSession(cookies=self.cookies, headers=self.headers) as session:
            start = datetime.now()
            endpoint = f"{self.base_url}/api/history/{job_id}"
            
            while True:
                if (datetime.now() - start).total_seconds() > timeout:
                    raise TimeoutError(f"Timeout after {timeout}s")
                
                async with session.get(endpoint) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(3)
                        continue
                    
                    result = await resp.json()
                    
                    # SMART URL DETECTION
                    video_url = None
                    if "generated_video" in result:
                        for video_item in result["generated_video"]:
                            if isinstance(video_item, dict):
                                for field in ['video_url', 'file_download_url', 'download_url']:
                                    if field in video_item and video_item[field]:
                                        video_url = video_item[field]
                                        break
                    
                    if video_url:
                        return video_url
                    
                    await asyncio.sleep(3)
    
    async def download_video(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"Download failed: HTTP {resp.status}")
                return await resp.read()
