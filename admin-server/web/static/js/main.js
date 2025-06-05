// main.js - Основной JavaScript файл

// Функция обновления статистики
function refreshStats() {
    fetch('/dashboard/api/stats')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                console.error('Ошибка обновления статистики:', data.error);
            }
        })
        .catch(error => {
            console.error('Ошибка запроса:', error);
        });
}

// Функция показа уведомлений
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container-fluid');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
    }
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Функция валидации IP адресов
function validateIP(ip) {
    const ipRegex = /^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/;
    return ipRegex.test(ip);
}

// Функция валидации CIDR
function validateCIDR(cidr) {
    const cidrRegex = /^(?:[0-9]{1,3}\.){3}[0-9]{1,3}\/[0-9]{1,2}$/;
    return cidrRegex.test(cidr);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Автообновление дашборда каждые 30 секунд
    if (window.location.pathname.includes('dashboard')) {
        setInterval(refreshStats, 30000);
    }
    
    // Инициализация tooltips Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});