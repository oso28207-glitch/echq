import re
import yt_dlp
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import logging
import time

logger = logging.getLogger(__name__)

BASE_URL = "https://k.3chk.net"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

class VideoExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def get_page_content(self, url):
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"فشل جلب الصفحة: {e}")
            return None

    def extract_best_video_url(self, episode_url):
        # 1. محاولة yt-dlp (لكن قد تفشل)
        result = self._extract_with_ytdlp(episode_url)
        if result:
            return result

        # 2. محاولة استخراج الرابط من الصفحة الوسيطة ثم متابعة السيرفر
        result = self._extract_from_intermediate(episode_url)
        if result:
            return result

        # 3. محاولة مباشرة (إذا كانت الصفحة تحتوي على iframe مباشر)
        result = self._extract_via_iframe(episode_url)
        if result:
            return result

        # 4. محاولة البحث المباشر
        result = self._extract_direct(episode_url)
        if result:
            return result

        return None

    def _extract_from_intermediate(self, episode_url):
        """معالجة الصفحات الوسيطة (التي تطلب الضغط على زر أو إعادة توجيه)"""
        html = self.get_page_content(episode_url)
        if not html:
            return None
        soup = BeautifulSoup(html, 'html.parser')

        # البحث عن روابط أو أزرار تؤدي إلى صفحة المشاهدة الفعلية
        # مثال: زر "مشاهدة الحلقة" أو رابط "اضغط هنا"
        watch_link = None
        # 1. البحث عن رابط داخل عنصر يحمل class="watch-btn" أو مشابه
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.text.strip()
            if 'مشاهدة' in text or 'اضغط' in text or 'watch' in text.lower():
                if href and not href.startswith('#'):
                    watch_link = href
                    break

        # 2. البحث عن نموذج (form) وإرساله
        if not watch_link:
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
                    if not action.startswith('http'):
                        action = urljoin(episode_url, action)
                    try:
                        resp = self.session.post(action, data=data, timeout=30, allow_redirects=True)
                        # بعد إرسال النموذج، نحصل على الصفحة النهائية (التي تحتوي على المشغل)
                        final_html = resp.text
                        final_url = resp.url
                        # الآن نستخرج السيرفر من الصفحة النهائية
                        server_url = self._extract_server_from_page(final_html, final_url)
                        if server_url:
                            return server_url
                    except Exception as e:
                        logger.error(f"خطأ في إرسال النموذج: {e}")

        # 3. إذا وجدنا رابط watch_link، نتابعه
        if watch_link:
            if not watch_link.startswith('http'):
                watch_link = urljoin(episode_url, watch_link)
            # جلب صفحة المشاهدة
            watch_html = self.get_page_content(watch_link)
            if watch_html:
                server_url = self._extract_server_from_page(watch_html, watch_link)
                if server_url:
                    return server_url

        # 4. إذا لم نجد رابطاً، نبحث عن iframe مباشر في الصفحة الوسيطة
        iframe = soup.find('iframe', src=True)
        if iframe:
            src = iframe.get('src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(episode_url, src)
                # متابعة iframe (قد يكون هو السيرفر نفسه)
                if 'camalk.net' in src:
                    return self._follow_camalk(src)
                return src

        # 5. البحث عن أي رابط يحوي 'embed' أو 'watch' في النص
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and ('embed' in href or 'watch' in href):
                if not href.startswith('http'):
                    href = urljoin(episode_url, href)
                # جلب هذه الصفحة واستخراج السيرفر
                page_html = self.get_page_content(href)
                if page_html:
                    server_url = self._extract_server_from_page(page_html, href)
                    if server_url:
                        return server_url

        return None

    def _extract_server_from_page(self, html, base_url):
        """استخراج رابط السيرفر (مثل vdesk.live أو camalk.net) من صفحة المشاهدة"""
        if not html:
            return None
        soup = BeautifulSoup(html, 'html.parser')

        # 1. البحث عن iframe (غالباً ما يكون هو السيرفر)
        iframe = soup.find('iframe', src=True)
        if iframe:
            src = iframe.get('src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(base_url, src)
                # إذا كان من camalk.net، نتابعه
                if 'camalk.net' in src:
                    return self._follow_camalk(src)
                return src

        # 2. البحث عن عنصر video
        video = soup.find('video', src=True)
        if video:
            return video.get('src')

        # 3. البحث داخل script عن روابط (قد تكون مشفرة)
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                content = script.string
                # البحث عن روابط سيرفرات معروفة
                match = re.search(r'(https?://(?:vdesk\.live|cdnplus\.space|anafast\.cyou|vidspeed\.space)[^\s"\']*)', content)
                if match:
                    return match.group(1)
                # البحث عن روابط .mp4, .m3u8
                match = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8|mkv|webm)[^\s"\']*)', content)
                if match:
                    return match.group(1)

        # 4. البحث عن أي رابط يحوي 'embed' أو 'player' أو 'server'
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href and ('embed' in href or 'player' in href or 'server' in href or 'camalk' in href):
                if not href.startswith('http'):
                    href = urljoin(base_url, href)
                if 'camalk.net' in href:
                    return self._follow_camalk(href)
                return href

        return None

    def _extract_with_ytdlp(self, url):
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
                video_url = info.get('url')
                if video_url:
                    return video_url
                formats = info.get('formats', [])
                if formats:
                    best = max(formats, key=lambda x: x.get('height', 0) or 0)
                    return best.get('url')
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
        html = self.get_page_content(episode_url)
        if not html:
            return None
        soup = BeautifulSoup(html, 'html.parser')
        iframe = soup.find('iframe', src=True)
        if not iframe:
            return None
        src = iframe.get('src')
        if not src:
            return None
        if not src.startswith('http'):
            src = urljoin(episode_url, src)
        if 'camalk.net' in src:
            return self._follow_camalk(src)
        return src

    def _follow_camalk(self, camalk_url):
        try:
            response = self.session.get(camalk_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form')
            if not form:
                iframe = soup.find('iframe', src=True)
                if iframe:
                    return iframe.get('src')
                return None

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
                final_response = self.session.post(action, data=data, timeout=30, allow_redirects=True)
                final_url = final_response.url
                final_html = final_response.text
                # استخراج السيرفر من الصفحة النهائية
                return self._extract_server_from_page(final_html, final_url)
            return None
        except Exception as e:
            logger.error(f"متابعة camalk فشلت: {e}")
            return None

    def _extract_direct(self, episode_url):
        html = self.get_page_content(episode_url)
        if not html:
            return None
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


def get_server_url(episode_url):
    extractor = VideoExtractor()
    return extractor.extract_best_video_url(episode_url)
