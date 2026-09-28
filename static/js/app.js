/* ==========================================================================
   CHECKEASE â€” Main Application JS (HTMX Integration)
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    console.log("Checkease HTMX Frontend initialized");
});

// Lắng nghe sự kiện sau khi HTMX swap DOM xong (Khởi tạo lại Alpine và Chart.js)
document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (window.Alpine && evt.detail && evt.detail.target) {
        window.Alpine.initTree(evt.detail.target);
    }
    if (document.getElementById('overview-chart')) {
        initOverviewChart();
    }
});

function initOverviewChart() {
    const container = document.getElementById('overview-chart');
    if(!container) return;
    
    let rawData = container.getAttribute('data-chart');
    if(!rawData) return;
    
    let chartData = JSON.parse(rawData);
    if(chartData.labels.length === 0) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-3);font-size:14px;border:1px dashed var(--border-2);border-radius:8px">ChÆ°a cÃ³ dá»¯ liá»‡u phÃ¢n tÃ­ch</div>';
        return;
    }
    
    const ctx = document.getElementById('overviewCanvas').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Final Score',
                data: chartData.scores,
                borderColor: '#2563eb',
                tension: 0.1,
                fill: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { min: 0, max: 100 }
            }
        }
    });
}

// Khá»Ÿi táº¡o láº§n Ä‘áº§u
initOverviewChart();


window.exportRealPdf = function(btn) {
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = 'Đang tạo PDF...';
    
    const projectId = btn.getAttribute('data-project-id');
    const vNum = btn.getAttribute('data-v-num');
    
    fetch('/api/v1/gate/export-pdf/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            project_id: projectId,
            w_test: parseFloat(btn.getAttribute('data-w-test')),
            w_code: parseFloat(btn.getAttribute('data-w-code')),
            pass_threshold: parseFloat(btn.getAttribute('data-pass-th')),
            warning_threshold: parseFloat(btn.getAttribute('data-warn-th'))
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Lỗi server');
        return response.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = 'checkease_report_v' + vNum + '.pdf';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    })
    .catch(error => {
        alert('Lỗi tạo báo cáo: ' + error);
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    });
};
