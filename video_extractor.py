import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
import time

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
            'Referer': BASE_URL,
        })

    def get_page_content(self, url):
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"فشل جلب الصفحة: {e}")
            return None

    def extract_video_url(self, episode_url):
        """الطريقة الرئيسية: استخراج رابط الفيديو من صفحة الحلقة"""
        
        # الخطوة 1: جلب صفحة الحلقة واستخراج رابط camalk.net
        html = self.get_page_content(episode_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        
        # البحث عن زر المشاهدة (الذي يؤدي إلى camalk.net)
        watch_btn = soup.find('a', class_='single-go-eps', href=True)
        if watch_btn:
            camalk_url = watch_btn.get('href')
            if camalk_url and 'camalk.net' in camalk_url:
                return self._extract_from_camalk(camalk_url)
        
        # البحث عن iframe مباشر
        iframe = soup.find('iframe', src=True)
        if iframe:
            src = iframe.get('src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(BASE_URL, src)
                if 'camalk.net' in src:
                    return self._extract_from_camalk(src)
                return self._extract_from_iframe(src)
        
        # البحث عن نموذج (form) داخل الصفحة (قد يكون مخفياً)
        form = soup.find('form', action=re.compile(r'camalk\.net'))
        if form:
            action = form.get('action')
            inputs = form.find_all('input')
            data = {inp.get('name'): inp.get('value', '') for inp in inputs if inp.get('name')}
            if action and data:
                return self._submit_form(action, data)
        
        return None

    def _extract_from_camalk(self, camalk_url):
        """استخراج الفيديو من صفحة camalk.net"""
        html = self.get_page_content(camalk_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        
        # البحث عن النموذج (form) الذي يعيد التوجيه
        form = soup.find('form', method=re.compile(r'post|get', re.I))
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
                if not action.startswith('http'):
                    action = urljoin(camalk_url, action)
                return self._submit_form(action, data)
        
        # إذا لم يكن هناك نموذج، نبحث عن iframe أو مشغل مباشر
        iframe = soup.find('iframe', src=True)
        if iframe:
            src = iframe.get('src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(camalk_url, src)
                return self._extract_from_iframe(src)
        
        # البحث عن رابط فيديو داخل script
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # البحث عن روابط m3u8 أو mp4
                match = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|mkv|webm)[^\s"\']*)', script.string)
                if match:
                    return match.group(1)
        
        return None

    def _submit_form(self, action, data):
        """إرسال نموذج ومتابعة إعادة التوجيه"""
        try:
            response = self.session.post(action, data=data, timeout=30, allow_redirects=True)
            final_url = response.url
            
            # محاولة استخراج الفيديو من الصفحة النهائية
            final_html = response.text
            final_soup = BeautifulSoup(final_html, 'html.parser')
            
            # البحث عن iframe
            iframe = final_soup.find('iframe', src=True)
            if iframe:
                src = iframe.get('src')
                if src:
                    if not src.startswith('http'):
                        src = urljoin(final_url, src)
                    return self._extract_from_iframe(src)
            
            # البحث عن عنصر video
            video = final_soup.find('video', src=True)
            if video:
                return video.get('src')
            
            # البحث عن روابط في script
            scripts = final_soup.find_all('script')
            for script in scripts:
                if script.string:
                    match = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|mkv|webm)[^\s"\']*)', script.string)
                    if match:
                        return match.group(1)
            
            return final_url
        except Exception as e:
            logger.error(f"فشل إرسال النموذج: {e}")
            return None

    def _extract_from_iframe(self, iframe_url):
        """استخراج الفيديو من صفحة iframe"""
        html = self.get_page_content(iframe_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        
        # البحث عن iframe داخل الصفحة
        inner_iframe = soup.find('iframe', src=True)
        if inner_iframe:
            src = inner_iframe.get('src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(iframe_url, src)
                # إذا كان الرابط لا يزال يشير إلى camalk.net، نعيد المحاولة
                if 'camalk.net' in src:
                    return self._extract_from_camalk(src)
                return src
        
        # البحث عن عنصر video
        video = soup.find('video', src=True)
        if video:
            return video.get('src')
        
        # البحث عن روابط في script
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                match = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|mkv|webm)[^\s"\']*)', script.string)
                if match:
                    return match.group(1)
        
        return None


# دالة سريعة للاستخدام
def get_server_url(episode_url):
    extractor = VideoExtractor()
    return extractor.extract_video_url(episode_url)


# مثال للاستخدام
if __name__ == "__main__":
    # اختبار مع حلقة حقيقية
    test_url = "https://k.3chk.net/video/ep/mslsl-ask-ve-mavi-mudblij-season-1-episode-4/"
    video_url = get_server_url(test_url)
    print(f"رابط الفيديو: {video_url}")
