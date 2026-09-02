/** PDFMaster Pro - frontend behavior (technical fixes only). */

let selectedFiles = [];
const MAX_FILE_BYTES = 100 * 1024 * 1024;

document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    if (uploadArea && fileInput) {
        uploadArea.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON' && e.target !== fileInput) fileInput.click();
        });
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
        fileInput.addEventListener('change', (e) => handleFiles(e.target.files));
    }

    document.querySelectorAll('.tool-card[data-tool-color]').forEach(card => {
        const color = card.dataset.toolColor;
        card.style.setProperty('--tool-color', color);
        const icon = card.querySelector('.tool-icon');
        if (icon) icon.style.background = `linear-gradient(135deg, ${color} 0%, ${color}cc 100%)`;
    });
    document.querySelectorAll('.tool-badge').forEach(badge => {
        if (badge.dataset.toolColor) badge.style.setProperty('--tool-color', badge.dataset.toolColor);
    });

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        });
    });
});

function handleFiles(fileList) {
    const files = Array.from(fileList || []).filter(Boolean);
    if (!files.length) return;

    const tooLarge = files.find(file => file.size > MAX_FILE_BYTES);
    if (tooLarge) {
        alert(`${tooLarge.name} exceeds the 100MB file limit.`);
        return;
    }

    const isMultiple = document.getElementById('toolMultiple').value === 'true';
    selectedFiles = isMultiple ? [...selectedFiles, ...files] : [files[0]];

    const toolId = document.getElementById('toolId')?.value;
    if (toolId === 'compare_pdf' && selectedFiles.length > 2) {
        selectedFiles = selectedFiles.slice(0, 2);
        alert('Compare PDFs accepts exactly two PDF files.');
    }
    updateFileList();
}

function updateFileList() {
    const fileList = document.getElementById('fileList');
    const fileItems = document.getElementById('fileItems');
    const toolOptions = document.getElementById('toolOptions');
    const convertSection = document.getElementById('convertSection');
    const uploadArea = document.getElementById('uploadArea');

    if (!fileList || !fileItems || !toolOptions || !convertSection || !uploadArea) return;
    if (!selectedFiles.length) {
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

        const icon = document.createElement('div');
        icon.className = 'file-item-icon';
        icon.textContent = getFileIcon(file.name);

        const info = document.createElement('div');
        info.className = 'file-item-info';
        const name = document.createElement('div');
        name.className = 'file-item-name';
        name.textContent = file.name;
        const size = document.createElement('div');
        size.className = 'file-item-size';
        size.textContent = formatFileSize(file.size);
        info.append(name, size);

        const remove = document.createElement('button');
        remove.className = 'file-item-remove';
        remove.type = 'button';
        remove.textContent = '✕';
        remove.addEventListener('click', () => removeFile(index));

        item.append(icon, info, remove);
        fileItems.appendChild(item);
    });
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
}

function clearFiles() {
    selectedFiles = [];
    const input = document.getElementById('fileInput');
    if (input) input.value = '';
    updateFileList();
}

function getFileIcon(filename) {
    const ext = (filename.split('.').pop() || '').toLowerCase();
    const icons = {
        pdf: '📄', doc: '📝', docx: '📝', xls: '📊', xlsx: '📊',
        ppt: '📽️', pptx: '📽️', jpg: '🖼️', jpeg: '🖼️', png: '🎨',
        gif: '🎭', bmp: '🖼️', webp: '🖼️', html: '🌐', htm: '🌐'
    };
    return icons[ext] || '📁';
}

function formatFileSize(bytes) {
    if (!bytes) return '0 Bytes';
    const units = ['Bytes', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${Math.round(bytes / Math.pow(1024, index) * 100) / 100} ${units[index]}`;
}

function startConversion() {
    if (!selectedFiles.length) {
        alert('Please select at least one file');
        return;
    }

    const toolId = document.getElementById('toolId').value;
    if (toolId === 'compare_pdf' && selectedFiles.length !== 2) {
        alert('Please select exactly two PDF files to compare.');
        return;
    }
    if (toolId === 'merge' && selectedFiles.length < 2) {
        alert('Please select at least two PDF files to merge.');
        return;
    }

    const formData = new FormData();
    formData.append('tool_id', toolId);
    selectedFiles.forEach(file => formData.append('files', file));

    const inputs = document.getElementById('optionsContainer').querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        if (!input.name || input.disabled) return;
        if (input.type === 'file') {
            if (input.files && input.files[0]) formData.append(input.name, input.files[0]);
        } else if ((input.type === 'checkbox' || input.type === 'radio')) {
            if (input.checked) formData.append(input.name, input.value);
        } else {
            formData.append(input.name, input.value);
        }
    });

    showProgress();
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress = Math.min(90, progress + Math.random() * 12);
        updateProgress(progress);
    }, 500);

    fetch('/convert', {method: 'POST', body: formData})
        .then(async response => {
            const contentType = response.headers.get('content-type') || '';
            let payload;
            if (contentType.includes('application/json')) {
                payload = await response.json();
            } else {
                payload = {success: false, error: await response.text() || response.statusText};
            }
            if (!response.ok) throw new Error(payload.error || `Server error ${response.status}`);
            return payload;
        })
        .then(data => {
            clearInterval(progressInterval);
            updateProgress(100);
            setTimeout(() => data.success ? showResult(data) : showError(data.error || 'Conversion failed'), 250);
        })
        .catch(error => {
            clearInterval(progressInterval);
            showError(error.message || 'Conversion failed');
        });
}

function showProgress() {
    ['uploadArea', 'fileList', 'toolOptions', 'convertSection', 'resultSection', 'errorSection'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    document.getElementById('progressSection').style.display = 'block';
}

function updateProgress(percent) {
    document.getElementById('progressFill').style.width = `${percent}%`;
    document.getElementById('progressText').textContent = `Processing... ${Math.round(percent)}%`;
}

function showResult(data) {
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('resultSection').style.display = 'block';
    document.getElementById('resultMessage').textContent = data.message || 'Your file is ready to download';
    const link = document.getElementById('downloadLink');
    link.href = data.download_url;
    link.download = data.filename || '';
}

function showError(message) {
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'block';
    document.getElementById('errorMessage').textContent = message;
}

function resetTool() {
    selectedFiles = [];
    const fileInput = document.getElementById('fileInput');
    if (fileInput) fileInput.value = '';
    const signatureInput = document.querySelector('input[name="signature_image"]');
    if (signatureInput) signatureInput.value = '';
    document.getElementById('uploadArea').style.display = 'block';
    ['fileList', 'toolOptions', 'convertSection', 'progressSection', 'resultSection', 'errorSection'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    document.getElementById('progressFill').style.width = '0%';
}

function toggleSignatureOptions() {
    const select = document.getElementById('sigTypeSelect');
    const textOptions = document.getElementById('textSigOptions');
    const imageOptions = document.getElementById('imageSigOptions');
    if (!select || !textOptions || !imageOptions) return;
    const imageMode = select.value === 'image';
    textOptions.style.display = imageMode ? 'none' : 'block';
    imageOptions.style.display = imageMode ? 'block' : 'none';
}
