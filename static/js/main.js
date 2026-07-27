/**
 * PDFMaster Pro - Frontend JavaScript
 */

let selectedFiles = [];

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    
    if (uploadArea && fileInput) {
        // Click to upload
        uploadArea.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON') {
                fileInput.click();
            }
        });
        
        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
        
        // File input change
        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });
    }
});

// ============================================
// FILE HANDLING
// ============================================

function handleFiles(files) {
    const isMultiple = document.getElementById('toolMultiple').value === 'true';
    
    if (!isMultiple) {
        selectedFiles = [files[0]];
    } else {
        selectedFiles = [...selectedFiles, ...Array.from(files)];
    }
    
    updateFileList();
}

function updateFileList() {
    const fileList = document.getElementById('fileList');
    const fileItems = document.getElementById('fileItems');
    const toolOptions = document.getElementById('toolOptions');
    const convertSection = document.getElementById('convertSection');
    const uploadArea = document.getElementById('uploadArea');
    
    if (selectedFiles.length === 0) {
        fileList.style.display = 'none';
        toolOptions.style.display = 'none';
        convertSection.style.display = 'none';
        uploadArea.style.display = 'block';
        return;
    }
    
    uploadArea.style.display = 'none';
    fileList.style.display = 'block';
    toolOptions.style.display = 'block';
    convertSection.style.display = 'block';
    
    fileItems.innerHTML = '';
    
    selectedFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `
            <div class="file-item-icon">${getFileIcon(file.name)}</div>
            <div class="file-item-info">
                <div class="file-item-name">${file.name}</div>
                <div class="file-item-size">${formatFileSize(file.size)}</div>
            </div>
            <button class="file-item-remove" onclick="removeFile(${index})">✕</button>
        `;
        fileItems.appendChild(item);
    });
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
}

function clearFiles() {
    selectedFiles = [];
    document.getElementById('fileInput').value = '';
    updateFileList();
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'pdf': '📄',
        'doc': '📝', 'docx': '📝',
        'xls': '📊', 'xlsx': '📊',
        'ppt': '📽️', 'pptx': '📽️',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🎨',
        'gif': '🎭', 'bmp': '🖼️',
        'html': '🌐', 'htm': '🌐'
    };
    return icons[ext] || '📁';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// ============================================
// CONVERSION
// ============================================

function startConversion() {
    if (selectedFiles.length === 0) {
        alert('Please select at least one file');
        return;
    }
    
    const toolId = document.getElementById('toolId').value;
    const formData = new FormData();
    
    formData.append('tool_id', toolId);
    
    // Append files
    selectedFiles.forEach(file => {
        formData.append('files', file);
    });
    
    // Append options
    const optionsContainer = document.getElementById('optionsContainer');
    const inputs = optionsContainer.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        if (input.name) {
            formData.append(input.name, input.value);
        }
    });
    
    // Show progress
    showProgress();
    
    // Simulate progress
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 90) progress = 90;
        updateProgress(progress);
    }, 300);
    
    // Send request
    fetch('/convert', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        clearInterval(progressInterval);
        updateProgress(100);
        
        setTimeout(() => {
            if (data.success) {
                showResult(data);
            } else {
                showError(data.error || 'Conversion failed');
            }
        }, 500);
    })
    .catch(error => {
        clearInterval(progressInterval);
        showError('Network error: ' + error.message);
    });
}

function showProgress() {
    document.getElementById('uploadArea').style.display = 'none';
    document.getElementById('fileList').style.display = 'none';
    document.getElementById('toolOptions').style.display = 'none';
    document.getElementById('convertSection').style.display = 'none';
    document.getElementById('progressSection').style.display = 'block';
    document.getElementById('resultSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';
}

function updateProgress(percent) {
    document.getElementById('progressFill').style.width = percent + '%';
    document.getElementById('progressText').textContent = `Processing... ${Math.round(percent)}%`;
}

function showResult(data) {
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('resultSection').style.display = 'block';
    document.getElementById('resultMessage').textContent = data.message || 'Your file is ready to download';
    document.getElementById('downloadLink').href = data.download_url;
    document.getElementById('downloadLink').download = data.filename;
}

function showError(message) {
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'block';
    document.getElementById('errorMessage').textContent = message;
}

function resetTool() {
    selectedFiles = [];
    document.getElementById('fileInput').value = '';
    document.getElementById('uploadArea').style.display = 'block';
    document.getElementById('fileList').style.display = 'none';
    document.getElementById('toolOptions').style.display = 'none';
    document.getElementById('convertSection').style.display = 'none';
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('resultSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';
    document.getElementById('progressFill').style.width = '0%';
}

// Toggle between Text and Image signature options
function toggleSignatureOptions() {
    const type = document.getElementById('sigTypeSelect').value;
    const textOptions = document.getElementById('textSigOptions');
    const imageOptions = document.getElementById('imageSigOptions');
    
    if (type === 'text') {
        textOptions.style.display = 'block';
        imageOptions.style.display = 'none';
    } else {
        textOptions.style.display = 'none';
        imageOptions.style.display = 'block';
    }
}



// ============================================
// TOOL CARD COLORS (replaces inline style)
// ============================================
document.querySelectorAll('.tool-card[data-tool-color]').forEach(card => {
    const color = card.dataset.toolColor;
    card.style.setProperty('--tool-color', color);
    const icon = card.querySelector('.tool-icon');
    if (icon) {
        icon.style.background = `linear-gradient(135deg, ${color} 0%, ${color}cc 100%)`;
    }
});

// Tool badge colors
document.querySelectorAll('.tool-badge').forEach(badge => {
    const color = badge.dataset.toolColor;
    if (color) {
        badge.style.setProperty('--tool-color', color);
    }
});

// ============================================
// SMOOTH SCROLL
// ============================================

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});