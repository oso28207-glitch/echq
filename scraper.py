import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://k.3chk.net"

def get_dubbed_series(page=1):
    """
    جلب قائمة المسلسلات المدبلجة من صفحة البحث
    تعيد قائمة من القواميس: [{"name": "اسم المسلسل", "url": "رابط المسلسل"}, ...]
    """
    search_url = f"{BASE_URL}/search/%D9%85%D8%AF%D8%A8%D9%84%D8%AC/page/{page}/"
    
    try:
        response = requests.get(search_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في جلب الصفحة: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    series_list = []

    # البحث عن عناصر المسلسلات
    blocks = soup.find_all('div', class_='EpisodeBlock')
    for block in blocks:
        link_tag = block.find('a')
        title_tag = block.find('div', class_='EpisodeBlockTitle')
        type_tag = block.find('div', class_='EPNumber')
        
        if link_tag and title_tag:
            name = title_tag.text.strip()
            url = link_tag.get('href')
            if not url.startswith('http'):
                url = BASE_URL + url
            
            # تحديد النوع (مسلسل / فلم)
            content_type = "مسلسل"
            if type_tag:
                type_text = type_tag.text.strip()
                if "فلم" in type_text or "فيلم" in type_text:
                    content_type = "فيلم"
            
            series_list.append({
                'name': name,
                'url': url,
                'type': content_type
            })

    logger.info(f"تم جلب {len(series_list)} مسلسل/فيلم من الصفحة {page}")
    return series_list

def get_series_episodes(series_url):
    """
    جلب قائمة حلقات مسلسل معين من صفحته
    تعيد قائمة من القواميس: [{"number": "1", "url": "رابط الحلقة"}, ...]
    """
    try:
        response = requests.get(series_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في جلب حلقات المسلسل: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    episodes = []

    # البحث عن روابط الحلقات (غالباً تكون في عناصر li أو div داخل قائمة)
    # قد يختلف الهيكل حسب المسلسل، نحاول عدة أنماط
    
    # النمط الشائع: روابط داخل ul مع class episodios
    episode_links = soup.find_all('a', href=True)
    for link in episode_links:
        href = link.get('href', '')
        text = link.text.strip()
        # نبحث عن أرقام حلقات في النص أو الرابط
        if href and '/watch/' in href:
            # استخراج رقم الحلقة من النص أو الرابط
            match = re.search(r'(\d+)', text)
            if not match:
                match = re.search(r'(\d+)', href)
            if match:
                episode_num = match.group(1)
                if not href.startswith('http'):
                    href = BASE_URL + href
                episodes.append({
                    'number': episode_num,
                    'url': href
                })
    
    # إذا لم نجد، نحاول البحث عن عناصر الفيديو في الصفحة
    if not episodes:
        video_blocks = soup.find_all('div', class_='episode-block')
        for block in video_blocks:
            link = block.find('a')
            if link and link.get('href'):
                href = link.get('href')
                text = link.text.strip()
                match = re.search(r'(\d+)', text)
                if match:
                    if not href.startswith('http'):
                        href = BASE_URL + href
                    episodes.append({
                        'number': match.group(1),
                        'url': href
                    })
    
    # ترتيب الحلقات حسب الرقم
    episodes.sort(key=lambda x: int(x['number']) if x['number'].isdigit() else 0)
    
    logger.info(f"تم جلب {len(episodes)} حلقة للمسلسل")
    return episodes

def extract_video_url(episode_url):
    """
    استخراج رابط الفيديو المباشر من صفحة الحلقة
    """
    try:
        response = requests.get(episode_url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"خطأ في جلب صفحة الحلقة: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # البحث عن iframe أو video source
    iframe = soup.find('iframe', src=True)
    if iframe:
        src = iframe.get('src')
        if src:
            return src
    
    # البحث عن عنصر الفيديو
    video = soup.find('video', src=True)
    if video:
        return video.get('src')
    
    # البحث عن روابط في script
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            # البحث عن رابط فيديو داخل script
            match = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8|mkv)[^\s"\']*)', script.string)
            if match:
                return match.group(1)
    
    return None
