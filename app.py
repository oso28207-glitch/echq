from flask import Flask, render_template, request, jsonify, Response, send_file, url_for
import threading
import json
import logging
import time
from pathlib import Path
import sys
import os

# إضافة المجلد الحالي إلى المسار
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scraper import get_dubbed_series, get_series_episodes, extract_video_url
from video_processor import process_video, delete_old_files

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB

# مجلدات مؤقتة
PROCESSED_DIR = Path("processed")
PROCESSED_DIR.mkdir(exist_ok=True)

# حالة المعالجة لكل مستخدم (في الإنتاج استخدم Redis)
progress_status = {
    "progress": 0,
    "message": "في انتظار الطلب",
    "video_path": None,
    "status": "idle",  # idle, processing, done, error
    "video_url": None
}

# قفل للتزامن
progress_lock = threading.Lock()

@app.route('/')
def index():
    """الصفحة الرئيسية تعرض قائمة المسلسلات"""
    series = get_dubbed_series(page=1)
    return render_template('index.html', series=series, base_url=request.host_url)

@app.route('/api/series')
def api_series():
    """API لجلب قائمة المسلسلات"""
    page = request.args.get('page', 1, type=int)
    series = get_dubbed_series(page=page)
    return jsonify(series)

@app.route('/api/episodes')
def api_episodes():
    """API لجلب حلقات مسلسل معين"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "رابط المسلسل مطلوب"}), 400
    
    episodes = get_series_episodes(url)
    return jsonify(episodes)

@app.route('/api/process', methods=['POST'])
def start_processing():
    """بدء معالجة حلقة (تحميل + ضغط)"""
    global progress_status
    
    data = request.get_json()
    video_url = data.get('url')
    if not video_url:
        return jsonify({"error": "رابط الفيديو مطلوب"}), 400
    
    # التحقق من وجود الفيديو في المصدر
    direct_url = extract_video_url(video_url)
    if not direct_url:
        return jsonify({"error": "لم يتم العثور على رابط الفيديو"}), 404
    
    # إعادة تعيين الحالة
    with progress_lock:
        progress_status = {
            "progress": 0,
            "message": "بدء المعالجة...",
            "video_path": None,
            "status": "processing",
            "video_url": direct_url
        }
    
    # تشغيل المعالجة في خلفية
    thread = threading.Thread(
        target=process_video_wrapper,
        args=(direct_url,)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"status": "started", "video_url": direct_url})

def process_video_wrapper(video_url):
    """دالة تغليف لمعالجة الفيديو مع تحديث الحالة"""
    global progress_status
    
    def update_progress(progress, message):
        with progress_lock:
            progress_status["progress"] = progress
            progress_status["message"] = message
    
    try:
        result_path = process_video(video_url, update_progress)
        with progress_lock:
            if result_path:
                progress_status["video_path"] = result_path
                progress_status["status"] = "done"
                progress_status["message"] = "اكتمل! يمكنك مشاهدة الفيديو."
            else:
                progress_status["status"] = "error"
                progress_status["message"] = "فشلت المعالجة!"
    except Exception as e:
        logger.error(f"خطأ في المعالجة: {e}")
        with progress_lock:
            progress_status["status"] = "error"
            progress_status["message"] = f"خطأ: {str(e)}"
    
    # حذف الملفات القديمة كل 10 معالجات (تقريباً)
    delete_old_files()

@app.route('/api/progress')
def progress_stream():
    """بث حالة التقدم باستخدام Server-Sent Events"""
    def generate():
        global progress_status
        last_progress = -1
        while True:
            with progress_lock:
                current = progress_status.copy()
            
            # إرسال التحديث فقط إذا تغير التقدم
            if current["progress"] != last_progress:
                last_progress = current["progress"]
                # إرسال كـ JSON
                yield f"data: {json.dumps(current)}\n\n"
            
            # إذا انتهت المعالجة أو حدث خطأ، ننهي البث بعد قليل
            if current["status"] in ["done", "error"]:
                # ننتظر 5 ثواني ثم ننهي
                time.sleep(5)
                # إرسال إشارة انتهاء
                yield f"data: {json.dumps({'status': 'closed'})}\n\n"
                break
            
            time.sleep(1)
    
    return Response(generate(), mimetype="text/event-stream")

@app.route('/api/watch/<filename>')
def watch_video(filename):
    """عرض الفيديو المضغوط"""
    file_path = PROCESSED_DIR / filename
    if not file_path.exists():
        return "الفيديو غير موجود", 404
    return send_file(file_path, as_attachment=False)

@app.route('/api/watch/<filename>/progress')
def watch_video_with_progress(filename):
    """عرض الفيديو مع شريط تقدم (يعيد صفحة HTML)"""
    # نستخدم ملف الفيديو الحالي أو نبحث عنه
    file_path = PROCESSED_DIR / filename
    if not file_path.exists():
        return "الفيديو غير موجود", 404
    
    # إعادة توجيه إلى صفحة المشاهدة
    video_url = url_for('watch_video', filename=filename)
    return render_template('watch.html', video_url=video_url)

@app.route('/api/cleanup', methods=['POST'])
def cleanup_files():
    """تنظيف الملفات القديمة يدوياً"""
    delete_old_files(max_age_hours=1)
    return jsonify({"status": "cleaned"})

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "الصفحة غير موجودة"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "خطأ في الخادم"}), 500

if __name__ == '__main__':
    # تنظيف عند بدء التشغيل
    delete_old_files(max_age_hours=24)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
