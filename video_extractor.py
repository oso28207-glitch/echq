import re
import yt_dlp
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://k.3chk.net"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

class VideoExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ar,en;q=0.9',
        })
    
    def get_page_content(self, url):
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"جلب الصفحة فشل: {e}")
            return None
    
    def extract_best_video_url(self, episode_url):
        """الدالة الرئيسية: استخراج أفضل رابط فيديو"""
        
        # الطريقة الأولى: استخدام yt-dlp (الأفضل)
        result = self._extract_with_ytdlp(episode_url)
        if result:
            return result
        
        # الطريقة الثانية: استخراج iframe ومتابعته
        result = self._extract_via_iframe(episode_url)
        if result:
            return result
        
        # الطريقة الثالثة: البحث المباشر
        result = self._extract_direct(episode_url)
        if result:
            return result
        
        return None
    
    def _extract_with_ytdlp(self, url):
        """استخدام yt-dlp للاستخراج"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
            'extract_flat': True,
            'user_agent': USER_AGENT,
            'ignoreerrors': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None
                
                # استخراج الرابط المباشر
                video_url = info.get('url')
                if video_url:
                    return video_url
                
                # محاولة من التنسيقات
                formats = info.get('formats', [])
                if formats:
                    # اختيار أفضل تنسيق
                    best = max(formats, key=lambda x: x.get('height', 0) or 0)
                    return best.get('url')
                
                # محاولة من الإدخالات
                entries = info.get('entries', [])
                if entries:
                    entry = entries[0]
                    video_url = entry.get('url')
                    if video_url:
                        return video_url
                    
                    formats = entry.get('formats', [])
                    if formats:
                        best = max(formats, key=lambda x: x.get('height', 0) or 0)
                        return best.get('url')
                
                return None
        except Exception as e:
            logger.error(f"yt-dlp error: {e}")
            return None
    
    def _extract_via_iframe(self, episode_url):
        """استخراج عبر iframe"""
        html = self.get_page_content(episode_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # العثور على iframe
        iframe = soup.find('iframe', src=True)
        if not iframe:
            return None
        
        src = iframe.get('src')
        if not src:
            return None
        
        if not src.startswith('http'):
            src = urljoin(BASE_URL, src)
        
        # إذا كان الرابط من camalk.net، نقوم بمتابعته
        if 'camalk.net' in src:
            return self._follow_camalk(src)
        
        # محاولة استخراج الفيديو من صفحة embed
        embed_html = self.get_page_content(src)
        if embed_html:
            embed_soup = BeautifulSoup(embed_html, 'html.parser')
            
            # البحث عن iframe داخل embed
            inner_iframe = embed_soup.find('iframe', src=True)
            if inner_iframe:
                inner_src = inner_iframe.get('src')
                if inner_src:
                    if not inner_src.startswith('http'):
                        inner_src = urljoin(BASE_URL, inner_src)
                    if 'camalk.net' in inner_src:
                        return self._follow_camalk(inner_src)
                    return inner_src
            
            # البحث عن فيديو مباشر
            video = embed_soup.find('video', src=True)
            if video:
                return video.get('src')
        
        return src
    
    def _follow_camalk(self, camalk_url):
        """متابعة إعادة التوجيه من camalk.net"""
        try:
            # جلب الصفحة الأولى
            response = self.session.get(camalk_url, timeout=30)
            
            # البحث عن النموذج وتنفيذ إعادة التوجيه
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form')
            
            if form:
                action = form.get('action', '')
                inputs = form.find_all('input')
                data = {}
                for inp in inputs:
                    name = inp.get('name')
                    value = inp.get('value', '')
                    if name:
                        data[name] = value
                
                if action and data:
                    # إرسال النموذج
                    if not action.startswith('http'):
                        action = urljoin(camalk_url, action)
                    
                    final_response = self.session.post(action, data=data, timeout=30, allow_redirects=True)
                    final_url = final_response.url
                    
                    # محاولة استخراج فيديو من الصفحة النهائية
                    final_html = final_response.text
                    final_soup = BeautifulSoup(final_html, 'html.parser')
                    
                    # البحث عن فيديو
                    video = final_soup.find('video', src=True)
                    if video:
                        return video.get('src')
                    
                    iframe = final_soup.find('iframe', src=True)
                    if iframe:
                        return iframe.get('src')
                    
                    # البحث عن روابط في script
                    scripts = final_soup.find_all('script')
                    for script in scripts:
                        if script.string:
                            match = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8|mkv|webm)[^\s"\']*)', script.string)
                            if match:
                                return match.group(1)
                    
                    return final_url
            
            return None
            
        except Exception as e:
            logger.error(f"متابعة camalk فشلت: {e}")
            return None
    
    def _extract_direct(self, episode_url):
        """استخراج مباشر من الصفحة"""
        html = self.get_page_content(episode_url)
        if not html:
            return None
        
        # البحث عن روابط فيديو مباشرة
        patterns = [
            r'(https?://[^\s"\']+\.mp4[^\s"\']*)',
            r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
            r'(https?://[^\s"\']+\.mkv[^\s"\']*)',
            r'(https?://[^\s"\']+\.webm[^\s"\']*)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html)
            if matches:
                return matches[0]
        
        return None


# دالة سريعة للاستخدام
def get_server_url(episode_url):
    """استخراج رابط السيرفر من رابط الحلقة"""
    extractor = VideoExtractor()
    return extractor.extract_best_video_url(episode_url)
