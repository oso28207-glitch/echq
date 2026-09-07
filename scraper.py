import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

BASE_URL = "https://k.3chk.net"

def get_series_list(page=1):
    """جلب قائمة المسلسلات المدبلجة"""
    url = f"{BASE_URL}/search/%D9%85%D8%AF%D8%A8%D9%84%D8%AC/page/{page}/"
    
    try:
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
    except Exception as e:
        logger.error(f"جلب المسلسلات فشل: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    series = []

    # البحث عن عناصر المسلسلات
    blocks = soup.find_all('div', class_='EpisodeBlock')
    if not blocks:
        blocks = soup.find_all('div', class_='item')

    for block in blocks:
        link = block.find('a', href=True)
        if not link:
            continue

        title_tag = block.find(['h2', 'h3', 'div'], class_=re.compile(r'title|EpisodeBlockTitle'))
        if not title_tag:
            title_tag = block.find(['h2', 'h3', 'div'])

        if title_tag:
            name = title_tag.text.strip()
            url = link.get('href')
            if not url.startswith('http'):
                url = BASE_URL + url

            # تحديد النوع
            type_tag = block.find('div', class_=re.compile(r'type|EPNumber'))
            content_type = "مسلسل"
            if type_tag and ('فلم' in type_tag.text or 'فيلم' in type_tag.text):
                content_type = "فيلم"

            series.append({
                'name': name,
                'url': url,
                'type': content_type
            })

    return series


def get_episodes(series_url):
    """جلب حلقات مسلسل معين"""
    try:
        response = requests.get(series_url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
    except Exception as e:
        logger.error(f"جلب الحلقات فشل: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    episodes = []

    # البحث عن أزرار الحلقات
    ep_boxes = soup.find_all('a', class_='EPNumber_box')
    for ep in ep_boxes:
        href = ep.get('href')
        num_span = ep.find('span')
        if href and num_span:
            num = num_span.text.strip()
            if not href.startswith('http'):
                href = BASE_URL + href
            episodes.append({
                'number': num,
                'url': href,
                'title': ep.get('title', f'الحلقة {num}')
            })

    # ترتيب تصاعدي
    episodes.sort(key=lambda x: int(x['number']) if x['number'].isdigit() else 0)
    return episodes


def get_series_info(series_url):
    """جلب معلومات المسلسل"""
    try:
        response = requests.get(series_url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
    except Exception as e:
        logger.error(f"جلب معلومات المسلسل فشل: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # استخراج اسم المسلسل
    title_tag = soup.find('h1', class_='title')
    if not title_tag:
        title_tag = soup.find('h1')
    
    name = title_tag.text.strip() if title_tag else "مسلسل"
    
    # استخراج الصورة
    img = soup.find('img', class_='ThumbBG')
    if not img:
        img = soup.find('img', src=re.compile(r'wp-content/uploads'))
    
    image = img.get('src') if img else None
    if image and not image.startswith('http'):
        image = BASE_URL + image
    
    # استخراج الوصف
    desc_tag = soup.find('div', class_='description')
    if not desc_tag:
        desc_tag = soup.find('p', class_='description')
    description = desc_tag.text.strip() if desc_tag else ""

    return {
        'name': name,
        'image': image,
        'description': description
    }
