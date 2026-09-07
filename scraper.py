import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://k.3chk.net"

def get_dubbed_series(page=1):
    """جلب قائمة المسلسلات المدبلجة من صفحة البحث"""
    search_url = f"{BASE_URL}/search/%D9%85%D8%AF%D8%A8%D9%84%D8%AC/page/{page}/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"فشل جلب المسلسلات: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    series_list = []

    # محاولة عدة أنماط للعثور على عناصر المسلسلات
    blocks = soup.find_all('div', class_='EpisodeBlock')
    if not blocks:
        blocks = soup.find_all('div', class_='item')
    if not blocks:
        blocks = soup.find_all('div', class_='post-item')

    for block in blocks:
        link_tag = block.find('a', href=True)
        if not link_tag:
            continue

        title_tag = block.find(['h2', 'h3', 'div'], class_=re.compile(r'title|name|EpisodeBlockTitle'))
        if not title_tag:
            title_tag = block.find(['h2', 'h3', 'div'])

        if title_tag:
            name = title_tag.text.strip()
            url = link_tag.get('href')
            if not url.startswith('http'):
                url = BASE_URL + url

            # استخراج النوع
            type_tag = block.find('div', class_=re.compile(r'type|EPNumber'))
            content_type = "مسلسل"
            if type_tag and ('فلم' in type_tag.text or 'فيلم' in type_tag.text):
                content_type = "فيلم"

            series_list.append({
                'name': name,
                'url': url,
                'type': content_type
            })

        if len(series_list) >= 30:
            break

    logger.info(f"تم جلب {len(series_list)} مسلسل من الصفحة {page}")
    return series_list


def get_series_episodes(series_url):
    """جلب قائمة حلقات مسلسل معين"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(series_url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"فشل جلب صفحة المسلسل: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    episodes = []

    # البحث عن روابط الحلقات بطرق متعددة

    # 1. البحث داخل قوائم الفصول (seasons)
    season_containers = soup.find_all('div', class_=re.compile(r'se-c|season|episode-list'))
    for container in season_containers:
        links = container.find_all('a', href=True)
        for link in links:
            href = link.get('href')
            text = link.text.strip()
            # نبحث عن أرقام في النص أو الرابط
            if href and ('/watch/' in href or '/video/' in href):
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

    # 2. إذا لم نجد، نبحث عن جميع الروابط التي تحتوي على "watch" أو "video"
    if not episodes:
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href')
            text = link.text.strip()
            if href and ('/watch/' in href or '/video/' in href):
                # نتأكد من أن النص يحتوي على رقم أو أنه ليس رابطاً لقسم آخر
                if re.search(r'\d+', text) or re.search(r'حلقة|episode', text, re.IGNORECASE):
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

    # 3. البحث في عناصر li داخل ul
    if not episodes:
        ul_lists = soup.find_all('ul', class_=re.compile(r'episodios|episodes|season'))
        for ul in ul_lists:
            for li in ul.find_all('li'):
                link = li.find('a', href=True)
                if link:
                    href = link.get('href')
                    text = link.text.strip()
                    if href and ('/watch/' in href or '/video/' in href):
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

    # إزالة التكرارات بناءً على الرابط
    seen = set()
    unique_episodes = []
    for ep in episodes:
        if ep['url'] not in seen:
            seen.add(ep['url'])
            unique_episodes.append(ep)

    # ترتيب حسب الرقم
    unique_episodes.sort(key=lambda x: int(x['number']) if x['number'].isdigit() else 0)

    logger.info(f"تم جلب {len(unique_episodes)} حلقة للمسلسل")
    return unique_episodes


def extract_video_url(episode_url):
    """استخراج رابط الفيديو المباشر من صفحة الحلقة"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(episode_url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"فشل جلب صفحة الحلقة: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # البحث عن iframe (المشغل الخارجي)
    iframe = soup.find('iframe', src=True)
    if iframe:
        src = iframe.get('src')
        if src:
            return src

    # البحث عن عنصر video
    video = soup.find('video', src=True)
    if video:
        return video.get('src')

    # البحث داخل script
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            match = re.search(r'(https?://[^\s"\']+\.(?:mp4|m3u8|mkv)[^\s"\']*)', script.string)
            if match:
                return match.group(1)

    return None
