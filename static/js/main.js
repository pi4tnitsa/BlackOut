// Основной JavaScript файл
document.addEventListener('DOMContentLoaded', function() {
    // Инициализация компонентов
    initializeComponents();
    
    // Автоматическое обновление статуса серверов
    if (document.querySelector('.server-status')) {
        setInterval(updateServerStatus, 30000); // Каждые 30 секунд
    }
    
    // Инициализация форм
    initializeForms();
});

function initializeComponents() {
    // Инициализация выпадающих списков
    const selects = document.querySelectorAll('select');
    selects.forEach(select => {
        select.addEventListener('change', function() {
            this.classList.add('changed');
        });
    });
    
    // Инициализация кнопок удаления
    const deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите удалить этот элемент?')) {
                e.preventDefault();
            }
        });
    });
}

// Функция для обновления статуса серверов
function updateServerStatus() {
    fetch('/api/servers/status')
        .then(response => response.json())
        .then(data => {
            updateServerStatusUI(data);
        })
        .catch(error => {
            console.error('Error updating server status:', error);
        });
}

// Функция для обновления UI статуса серверов
function updateServerStatusUI(data) {
    const statusElements = document.querySelectorAll('.server-status');
    statusElements.forEach(element => {
        const serverId = element.dataset.serverId;
        const status = data[serverId]?.status || 'offline';
        
        // Обновляем класс и текст
        element.className = `server-status status-${status}`;
        element.textContent = status === 'online' ? 'Онлайн' : 'Оффлайн';
    });
}

// Функция для инициализации форм
function initializeForms() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('error');
                } else {
                    field.classList.remove('error');
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('Пожалуйста, заполните все обязательные поля');
            }
        });
    });
}

// Функция для отображения уведомлений
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.textContent = message;
    
    const container = document.querySelector('.container');
    container.insertBefore(notification, container.firstChild);
    
    // Автоматическое скрытие через 5 секунд
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Функция для обновления задач
function updateTasks() {
    fetch('/api/tasks/status')
        .then(response => response.json())
        .then(data => {
            const taskElements = document.querySelectorAll('.task-status');
            taskElements.forEach(element => {
                const taskId = element.dataset.taskId;
                const status = data[taskId]?.status || 'pending';
                
                element.className = `task-status status-${status}`;
                element.textContent = getStatusText(status);
            });
        })
        .catch(error => {
            console.error('Error updating tasks:', error);
        });
}

// Функция для получения текста статуса
function getStatusText(status) {
    const statusMap = {
        'pending': 'Ожидает',
        'running': 'Выполняется',
        'completed': 'Завершено',
        'failed': 'Ошибка'
    };
    return statusMap[status] || status;
}

// Функция для обновления статистики
function updateStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // Обновляем статистику на странице
            Object.entries(data).forEach(([key, value]) => {
                const element = document.querySelector(`.stat-${key}`);
                if (element) {
                    element.textContent = value;
                }
            });
        })
        .catch(error => {
            console.error('Error updating stats:', error);
        });
}

// Функция для экспорта данных
function exportData(type) {
    fetch(`/api/export/${type}`)
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${type}_export_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        })
        .catch(error => {
            console.error('Error exporting data:', error);
            showNotification('Ошибка при экспорте данных', 'danger');
        });
} 