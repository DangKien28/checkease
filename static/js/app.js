/* ==========================================================================
   CHECKEASE — Main Application JS (HTMX Integration)
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    console.log("Checkease HTMX Frontend initialized");
});

// Lắng nghe sự kiện sau khi HTMX swap DOM xong (Dùng để khởi tạo lại JS plugin như Chart.js)
document.body.addEventListener('htmx:afterSwap', function(evt) {
    const target = evt.detail.target;
    
    // Ví dụ: Nếu có thẻ div vẽ biểu đồ mới được load vào, ta khởi tạo Chart ở đây
    if (target.querySelector('#overview-chart')) {
        initOverviewChart();
    }
});

function initOverviewChart() {
    // Sẽ gọi Chart.js ở đây khi có data thật
    console.log("Initialize Chart.js...");
    const container = document.getElementById('overview-chart');
    if(container) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-3);font-size:14px;border:1px dashed var(--border-2);border-radius:8px">Biểu đồ đang chờ kết nối Backend</div>';
    }
}

// Khởi tạo lần đầu
initOverviewChart();
