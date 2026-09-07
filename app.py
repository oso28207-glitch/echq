from flask import Flask, render_template, request, jsonify, send_file, url_for
import os
import logging
from pathlib import Path
import time

from scraper import get_series_list, get_episodes, get_series_info
from video_extractor import get_server_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# مجلد الفيديوهات المؤقتة
VIDEO_DIR = Path("downloads")
VIDEO_DIR.mkdir(exist_ok=True)

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    series = get_series_list(page=1)
    return render_template('index.html', series=series)

@app.route('/api/series')
def api_series():
    """API: جلب المسلسلات"""
    page = request.args.get('page', 1, type=int)
    series = get_series_list(page=page)
    return jsonify(series)

@app.route('/api/episodes')
def api_episodes():
    """API: جلب حلقات مسلسل"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'رابط المسلسل مطلوب'}), 400
    
    episodes = get_episodes(url)
    series_info = get_series_info(url)
    
    return jsonify({
        'series': series_info,
        'episodes': episodes
    })

@app.route('/api/video')
def api_video():
    """API: استخراج رابط الفيديو"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'رابط الحلقة مطلوب'}), 400
    
    video_url = get_server_url(url)
    if video_url:
        return jsonify({
            'success': True,
            'video_url': video_url
        })
    else:
        return jsonify({
            'success': False,
            'error': 'لم يتم العثور على رابط الفيديو'
        }), 404

@app.route('/watch')
def watch():
    """صفحة المشاهدة"""
    episode_url = request.args.get('url')
    if not episode_url:
        return "رابط الحلقة مطلوب", 400
    
    # استخراج رابط الفيديو
    video_url = get_server_url(episode_url)
    
    return render_template('watch.html', 
                         video_url=video_url,
                         episode_url=episode_url)

@app.route('/api/proxy/video')
def proxy_video():
    """وكيل لتحميل الفيديو"""
    url = request.args.get('url')
    if not url:
        return "رابط مطلوب", 400
    
    try:
        import requests
        response = requests.get(url, stream=True, timeout=30)
        return response.content
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return "خطأ في تحميل الفيديو", 500

@app.errorhandler(404)
def not_found(e):
    return render_template('index.html', series=[]), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'خطأ في الخادم'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
