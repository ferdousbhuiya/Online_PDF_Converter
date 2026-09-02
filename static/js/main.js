/** PDFMaster Pro - frontend behavior. */

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

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        });
    });

    initializeSignaturePreview();
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
    if (toolId === 'fill_pdf' && selectedFiles[0]) inspectFillablePdf(selectedFiles[0]);
    if (toolId === 'edit_metadata' && selectedFiles[0]) inspectPdfMetadata(selectedFiles[0]);
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
    if (!selectedFiles.length) {
        resetFillFields();
        resetMetadataFields();
    }
}

function clearFiles() {
    selectedFiles = [];
    const input = document.getElementById('fileInput');
    if (input) input.value = '';
    resetFillFields();
    resetMetadataFields();
    updateFileList();
}

function getFileIcon(filename) {
    const ext = (filename.split('.').pop() || '').toLowerCase();
    const icons = {pdf:'📄',doc:'📝',docx:'📝',xls:'📊',xlsx:'📊',ppt:'📽️',pptx:'📽️',jpg:'🖼️',jpeg:'🖼️',png:'🎨',gif:'🎭',bmp:'🖼️',webp:'🖼️',html:'🌐',htm:'🌐'};
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
    if (toolId === 'fill_pdf') collectFillFieldValues();

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
            if (contentType.includes('application/json')) payload = await response.json();
            else payload = {success: false, error: await response.text() || response.statusText};
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
    ['uploadArea','fileList','toolOptions','convertSection','resultSection','errorSection'].forEach(id => {
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
    resetFillFields();
    resetMetadataFields();
    document.getElementById('uploadArea').style.display = 'block';
    ['fileList','toolOptions','convertSection','progressSection','resultSection','errorSection'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    document.getElementById('progressFill').style.width = '0%';
}

function initializeSignaturePreview() {
    const dateInput = document.getElementById('signatureDate');
    if (dateInput && !dateInput.value) {
        const now = new Date();
        dateInput.value = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
    }
    updateSignaturePreview();
}

function toggleSignatureOptions() {
    const select = document.getElementById('sigTypeSelect');
    const textOptions = document.getElementById('textSigOptions');
    const imageOptions = document.getElementById('imageSigOptions');
    if (!select || !textOptions || !imageOptions) return;
    const imageMode = select.value === 'image';
    textOptions.style.display = imageMode ? 'none' : 'block';
    imageOptions.style.display = imageMode ? 'block' : 'none';
    if (!imageMode) updateSignaturePreview();
}

function updateSignaturePreview() {
    const preview = document.getElementById('signaturePreview');
    if (!preview) return;
    const text = document.getElementById('signatureText')?.value.trim() || 'Your Name';
    const style = document.getElementById('signatureStyle')?.value || 'formal';
    const font = document.getElementById('signatureFont')?.value || 'Helvetica-Oblique';
    const size = Number(document.getElementById('signatureSize')?.value || 30);
    const includeDate = document.getElementById('includeSignatureDate')?.value === 'yes';
    const dateValue = document.getElementById('signatureDate')?.value;
    const nameEl = document.getElementById('signaturePreviewName');
    const lineEl = document.getElementById('signaturePreviewLine');
    const metaEl = document.getElementById('signaturePreviewMeta');
    const dateEl = document.getElementById('signaturePreviewDate');

    nameEl.textContent = text;
    nameEl.style.fontFamily = font === 'Times-Italic' ? 'Georgia, serif' : font === 'Courier-Oblique' ? 'Courier New, monospace' : 'cursive';
    nameEl.style.fontSize = `${Math.max(22, Math.min(48, size * 1.05))}px`;
    lineEl.style.display = style === 'classic' ? 'none' : 'block';
    metaEl.style.display = style === 'classic' ? 'none' : 'flex';
    if (dateEl) {
        if (style === 'formal' && includeDate && dateValue) {
            const d = new Date(`${dateValue}T12:00:00`);
            dateEl.textContent = d.toLocaleDateString(undefined, {year:'numeric', month:'short', day:'numeric'});
        } else dateEl.textContent = '';
    }
}

function updateSignatureImagePreview(input) {
    const wrap = document.getElementById('signatureImagePreviewWrap');
    const img = document.getElementById('signatureImagePreview');
    if (!wrap || !img || !input.files?.[0]) return;
    img.src = URL.createObjectURL(input.files[0]);
    wrap.style.display = 'block';
}

async function inspectFillablePdf(file) {
    const status = document.getElementById('fillPdfStatus');
    const container = document.getElementById('fillFieldsContainer');
    if (!status || !container) return;
    status.textContent = 'Detecting fillable fields…';
    container.innerHTML = '';
    const body = new FormData();
    body.append('file', file);
    try {
        const response = await fetch('/pdf-fields', {method:'POST', body});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Unable to inspect this PDF');
        if (!data.fields.length) {
            status.textContent = 'No interactive form fields were found in this PDF.';
            return;
        }
        status.textContent = `${data.count} fillable field${data.count === 1 ? '' : 's'} detected.`;
        data.fields.forEach(renderFillField);
    } catch (error) {
        status.textContent = error.message || 'Unable to detect PDF form fields.';
    }
}

function renderFillField(field) {
    const container = document.getElementById('fillFieldsContainer');
    const group = document.createElement('div');
    group.className = 'option-group fill-field';
    const label = document.createElement('label');
    label.textContent = field.label || field.name;
    let input;

    if (field.type === 'choice' && field.options?.length) {
        input = document.createElement('select');
        input.className = 'form-control';
        const blank = document.createElement('option');
        blank.value = '';
        blank.textContent = 'Select…';
        input.appendChild(blank);
        field.options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt.value;
            option.textContent = opt.label;
            input.appendChild(option);
        });
    } else if (field.type === 'button') {
        input = document.createElement('select');
        input.className = 'form-control';
        const off = document.createElement('option');
        off.value = '/Off';
        off.textContent = 'Unchecked';
        input.appendChild(off);
        (field.button_options || ['/Yes']).forEach(value => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = 'Checked';
            input.appendChild(option);
        });
    } else {
        input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control';
        input.value = field.value && field.value !== 'None' ? field.value : '';
    }

    input.dataset.pdfField = field.name;
    group.append(label, input);
    container.appendChild(group);
}

function collectFillFieldValues() {
    const hidden = document.getElementById('fillFieldValues');
    if (!hidden) return;
    const values = {};
    document.querySelectorAll('[data-pdf-field]').forEach(input => {
        values[input.dataset.pdfField] = input.value;
    });
    hidden.value = JSON.stringify(values);
}

function resetFillFields() {
    const container = document.getElementById('fillFieldsContainer');
    const status = document.getElementById('fillPdfStatus');
    const hidden = document.getElementById('fillFieldValues');
    if (container) container.innerHTML = '';
    if (status) status.textContent = 'Select a PDF with interactive form fields. PDFMaster Pro will detect the fields automatically.';
    if (hidden) hidden.value = '{}';
}

async function inspectPdfMetadata(file) {
    const status = document.getElementById('metadataStatus');
    if (!status) return;
    resetMetadataFields(false);
    status.textContent = 'Reading current PDF metadata…';
    const body = new FormData();
    body.append('file', file);

    try {
        const response = await fetch('/pdf-metadata', {method:'POST', body});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Unable to inspect PDF metadata');
        const metadata = data.metadata || {};
        const mapping = {
            title: 'metadataTitle',
            author: 'metadataAuthor',
            subject: 'metadataSubject',
            keywords: 'metadataKeywords',
            creator: 'metadataCreator',
            producer: 'metadataProducer'
        };
        Object.entries(mapping).forEach(([key, id]) => {
            const input = document.getElementById(id);
            if (input) input.value = metadata[key] || '';
        });
        status.textContent = data.populated_count
            ? `${data.populated_count} existing metadata field${data.populated_count === 1 ? '' : 's'} loaded. Edit any value or choose Remove all metadata.`
            : 'No standard metadata values were found. You can add new metadata below.';
    } catch (error) {
        status.textContent = error.message || 'Unable to read metadata from this PDF.';
    }
}

function toggleMetadataRemoval() {
    const checkbox = document.getElementById('removeAllMetadata');
    const fields = document.querySelectorAll('#metadataFields input');
    const removing = Boolean(checkbox?.checked);
    fields.forEach(input => input.disabled = removing);
    const status = document.getElementById('metadataStatus');
    if (status && removing) status.textContent = 'All stored PDF metadata will be removed. The visible document content will not change.';
    if (status && !removing && selectedFiles[0]) inspectPdfMetadata(selectedFiles[0]);
}

function resetMetadataFields(resetStatus = true) {
    ['metadataTitle','metadataAuthor','metadataSubject','metadataKeywords','metadataCreator','metadataProducer'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.value = '';
            input.disabled = false;
        }
    });
    const checkbox = document.getElementById('removeAllMetadata');
    if (checkbox) checkbox.checked = false;
    const status = document.getElementById('metadataStatus');
    if (status && resetStatus) status.textContent = 'Select a PDF. Its current metadata will be loaded automatically.';
}