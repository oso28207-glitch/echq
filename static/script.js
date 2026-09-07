// متغيرات عامة
let currentPage = 1;
let isLoading = false;
let eventSource = null;

// عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    // تفعيل النقر على بطاقات المسلسلات
    document.querySelectorAll('.series-card').forEach(card => {
        card.addEventListener('click', function() {
            const url = this.dataset.url;
            const name = this.dataset.name;
            showEpisodes(url, name);
        });
    });

    // زر تحميل المزيد
    document.getElementById('load-more').addEventListener('click', function() {
        loadMoreSeries();
    });

    // تفعيل النوافذ المنبثقة
    window.episodesModal = new bootstrap.Modal(document.getElementById('episodesModal'));
    window.progressModal = new bootstrap.Modal(document.getElementById('progressModal'));
});

// عرض حلقات المسلسل
async function showEpisodes(seriesUrl, seriesName) {
    document.getElementById('episodesModalLabel').textContent = `حلقات: ${seriesName}`;
    document.getElementById('episodes-list').innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-danger" role="status">
                <span class="visually-hidden">جاري التحميل...</span>
            </div>
        </div>
    `;
    window.episodesModal.show();

    try {
        const response = await fetch(`/api/episodes?url=${encodeURIComponent(seriesUrl)}`);
        const episodes = await response.json();

        if (episodes.length === 0) {
            document.getElementById('episodes-list').innerHTML = `
                <div class="alert alert-warning">لا توجد حلقات متاحة لهذا المسلسل.</div>
            `;
            return;
        }

        // عرض الحلقات كأزرار
        let html = '<div class="d-flex flex-wrap justify-content-center">';
        episodes.forEach(ep => {
            html += `
                <div class="episode-item">
                    <button class="btn btn-outline-danger episode-btn" 
                            data-url="${ep.url}"
                            data-number="${ep.number}"
                            onclick="playEpisode(this)">
                        ${ep.number}
                    </button>
                </div>
            `;
        });
        html += '</div>';
        document.getElementById('episodes-list').innerHTML = html;

    } catch (error) {
        console.error('خطأ في جلب الحلقات:', error);
        document.getElementById('episodes-list').innerHTML = `
            <div class="alert alert-danger">حدث خطأ في تحميل الحلقات. حاول مرة أخرى.</div>
        `;
    }
}

// تشغيل حلقة (بدء التحميل والضغط)
async function playEpisode(button) {
    const url = button.dataset.url;
    const number = button.dataset.number;

    // عرض نافذة التقدم
    const progressModal = window.progressModal;
    document.getElementById('progress-status').textContent = '⏳ جارٍ التحضير...';
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-bar').textContent = '0%';
    document.getElementById('watch-link').style.display = 'none';
    progressModal.show();

    // إغلاق نافذة الحلقات
    window.episodesModal.hide();

    try {
        // بدء المعالجة
        const processResponse = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });
        const processData = await processResponse.json();

        if (processData.error) {
            document.getElementById('progress-status').textContent = '❌ ' + processData.error;
            document.getElementById('progress-bar').classList.remove('bg-success');
            document.getElementById('progress-bar').classList.add('bg-danger');
            return;
        }

        // استقبال التقدم عبر SSE
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource('/api/progress');
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            console.log('Progress:', data);

            // تحديث شريط التقدم
            document.getElementById('progress-bar').style.width = data.progress + '%';
            document.getElementById('progress-bar').textContent = data.progress + '%';
            document.getElementById('progress-status').textContent = data.message;

            // إذا انتهت المعالجة
            if (data.status === 'done' && data.video_path) {
                // استخراج اسم الملف
                const filename = data.video_path.split('/').pop();
                const watchUrl = `/api/watch/${filename}`;
                
                document.getElementById('watch-link').href = watchUrl;
                document.getElementById('watch-link').style.display = 'inline-block';
                document.getElementById('progress-bar').classList.remove('progress-bar-animated');
                document.getElementById('progress-status').textContent = '✅ ' + data.message;
                eventSource.close();
            } else if (data.status === 'error') {
                document.getElementById('progress-status').textContent = '❌ ' + data.message;
                document.getElementById('progress-bar').classList.remove('bg-success');
                document.getElementById('progress-bar').classList.add('bg-danger');
                eventSource.close();
            } else if (data.status === 'closed') {
                eventSource.close();
            }
        };

        eventSource.onerror = function() {
            console.warn('SSE connection closed.');
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        };

    } catch (error) {
        console.error('خطأ في بدء المعالجة:', error);
        document.getElementById('progress-status').textContent = '❌ حدث خطأ في الخادم.';
        document.getElementById('progress-bar').classList.remove('bg-success');
        document.getElementById('progress-bar').classList.add('bg-danger');
    }
}

// تحميل المزيد من المسلسلات
async function loadMoreSeries() {
    if (isLoading) return;
    isLoading = true;

    currentPage++;
    const button = document.getElementById('load-more');
    button.textContent = 'جاري التحميل...';
    button.disabled = true;

    try {
        const response = await fetch(`/api/series?page=${currentPage}`);
        const series = await response.json();

        if (series.length === 0) {
            button.textContent = 'لا يوجد المزيد';
            button.disabled = true;
            return;
        }

        const container = document.getElementById('series-list');
        series.forEach(item => {
            const col = document.createElement('div');
            col.className = 'col-6 col-md-3 col-lg-2 mb-3';
            col.innerHTML = `
                <div class="series-card card h-100" data-url="${item.url}" data-name="${item.name}">
                    <div class="card-body text-center">
                        <i class="bi bi-play-circle-fill display-4 text-danger"></i>
                        <h6 class="card-title mt-2">${item.name}</h6>
                        <span class="badge bg-secondary">${item.type}</span>
                    </div>
                </div>
            `;
            container.appendChild(col);

            // تفعيل الحدث للبطاقة الجديدة
            const card = col.querySelector('.series-card');
            card.addEventListener('click', function() {
                const url = this.dataset.url;
                const name = this.dataset.name;
                showEpisodes(url, name);
            });
        });

        button.textContent = 'تحميل المزيد';
        button.disabled = false;
        isLoading = false;

    } catch (error) {
        console.error('خطأ في تحميل المزيد:', error);
        button.textContent = 'حدث خطأ، حاول مرة أخرى';
        button.disabled = false;
        isLoading = false;
    }
}
