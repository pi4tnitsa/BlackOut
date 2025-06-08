// Nuclei Controller Main JavaScript

// Global variables
let refreshIntervals = {};

// Document ready
$(document).ready(function() {
    // Initialize tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();
    
    // Initialize popovers
    $('[data-bs-toggle="popover"]').popover();
    
    // Add fade-in animation to cards
    $('.card').addClass('fade-in');
    
    // Auto-hide alerts after 5 seconds
    $('.alert:not(.alert-permanent)').delay(5000).fadeOut('slow');
    
    // Initialize data tables if present
    if ($('#resultsTable').length) {
        initializeDataTable();
    }
    
    // Set up AJAX defaults
    $.ajaxSetup({
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    });
    
    // Handle AJAX errors globally
    $(document).ajaxError(function(event, jqXHR, ajaxSettings, thrownError) {
        if (jqXHR.status === 401) {
            // Redirect to login on authentication error
            window.location.href = '/login';
        }
    });
});

// Initialize DataTable for results
function initializeDataTable() {
    // Add search functionality to results table
    $('#resultsTable').on('keyup', '.search-input', function() {
        const value = $(this).val().toLowerCase();
        const column = $(this).data('column');
        
        $('#resultsTable tbody tr').filter(function() {
            $(this).toggle($(this).find('td').eq(column).text().toLowerCase().indexOf(value) > -1);
        });
    });
}

// Show loading overlay
function showLoading(message = 'Loading...') {
    const loadingHtml = `
        <div id="loadingOverlay" class="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" style="background: rgba(0,0,0,0.5); z-index: 9999;">
            <div class="text-center text-white">
                <div class="spinner-border text-light mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <h5>${message}</h5>
            </div>
        </div>
    `;
    $('body').append(loadingHtml);
}

// Hide loading overlay
function hideLoading() {
    $('#loadingOverlay').remove();
}

// Show notification
function showNotification(message, type = 'info') {
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    }[type] || 'alert-info';
    
    const icon = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    }[type] || 'fa-info-circle';
    
    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show position-fixed top-0 end-0 m-3" style="z-index: 9999;">
            <i class="fas ${icon}"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    $('body').append(alertHtml);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        $('.alert').last().fadeOut('slow', function() {
            $(this).remove();
        });
    }, 5000);
}

// Confirm dialog
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Update progress bar
function updateProgressBar(selector, progress) {
    const progressBar = $(selector).find('.progress-bar');
    progressBar.css('width', progress + '%');
    progressBar.text(Math.round(progress) + '%');
}

// Handle file upload with progress
function uploadFileWithProgress(url, formData, onProgress, onSuccess, onError) {
    $.ajax({
        url: url,
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        xhr: function() {
            const xhr = new window.XMLHttpRequest();
            xhr.upload.addEventListener('progress', function(evt) {
                if (evt.lengthComputable) {
                    const percentComplete = (evt.loaded / evt.total) * 100;
                    if (onProgress) onProgress(percentComplete);
                }
            }, false);
            return xhr;
        },
        success: onSuccess,
        error: onError
    });
}

// Auto-refresh functionality
function startAutoRefresh(elementId, url, interval = 5000) {
    const refreshFunction = function() {
        $.get(url, function(data) {
            $(elementId).html(data);
        });
    };
    
    // Initial refresh
    refreshFunction();
    
    // Set interval
    refreshIntervals[elementId] = setInterval(refreshFunction, interval);
}

function stopAutoRefresh(elementId) {
    if (refreshIntervals[elementId]) {
        clearInterval(refreshIntervals[elementId]);
        delete refreshIntervals[elementId];
    }
}

// Copy to clipboard
function copyToClipboard(text) {
    const textarea = $('<textarea>').val(text).css({
        position: 'fixed',
        opacity: 0
    }).appendTo('body');
    
    textarea[0].select();
    document.execCommand('copy');
    textarea.remove();
    
    showNotification('Copied to clipboard!', 'success');
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Search functionality
function initializeSearch(inputSelector, targetSelector, searchableSelector) {
    $(inputSelector).on('keyup', debounce(function() {
        const searchTerm = $(this).val().toLowerCase();
        
        $(targetSelector).each(function() {
            const searchableText = $(this).find(searchableSelector).text().toLowerCase();
            
            if (searchableText.includes(searchTerm)) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    }, 300));
}

// Export table to CSV
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    let csv = [];
    
    // Get headers
    const headers = [];
    $(table).find('thead th').each(function() {
        headers.push($(this).text().trim());
    });
    csv.push(headers.join(','));
    
    // Get rows
    $(table).find('tbody tr:visible').each(function() {
        const row = [];
        $(this).find('td').each(function() {
            let value = $(this).text().trim();
            // Escape quotes and wrap in quotes if contains comma
            if (value.includes(',') || value.includes('"')) {
                value = '"' + value.replace(/"/g, '""') + '"';
            }
            row.push(value);
        });
        csv.push(row.join(','));
    });
    
    // Download CSV
    const csvContent = csv.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'export.csv';
    a.click();
    URL.revokeObjectURL(url);
}

// WebSocket connection for real-time updates (future enhancement)
function initializeWebSocket(url) {
    const ws = new WebSocket(url);
    
    ws.onopen = function() {
        console.log('WebSocket connected');
    };
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = function() {
        console.log('WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        setTimeout(() => initializeWebSocket(url), 5000);
    };
    
    return ws;
}

function handleWebSocketMessage(data) {
    // Handle different message types
    switch (data.type) {
        case 'task_update':
            updateTaskStatus(data.task_id, data.status, data.progress);
            break;
        case 'worker_status':
            updateWorkerStatus(data.worker_id, data.status);
            break;
        case 'new_result':
            addNewResult(data.result);
            break;
    }
}

// Helper functions for WebSocket updates
function updateTaskStatus(taskId, status, progress) {
    // Update task status in UI
    const taskRow = $(`tr[data-task-id="${taskId}"]`);
    if (taskRow.length) {
        // Update status badge
        // Update progress bar
        updateProgressBar(taskRow.find('.progress'), progress);
    }
}

function updateWorkerStatus(workerId, status) {
    // Update worker status in UI
    const workerRow = $(`tr[data-worker-id="${workerId}"]`);
    if (workerRow.length) {
        // Update status badge
    }
}

function addNewResult(result) {
    // Add new result to table
    // Show notification
    showNotification(`New ${result.severity} finding: ${result.template_name}`, 'warning');
}