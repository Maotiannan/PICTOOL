// 引入jsPDF库
const { jsPDF } = window.jspdf;

// 全局变量
let imageFiles = []; // 存储图片文件
let selectedIndex = -1; // 当前选中的图片索引
let thumbnailCache = {}; // 缓存缩略图URL
let pdfWorker = null; // PDF生成Web Worker

// DOM元素
const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const previewList = document.getElementById('preview-list');
const selectedImagePreview = document.getElementById('selected-image-preview');
const pdfNameInput = document.getElementById('pdf-name');
const generateBtn = document.getElementById('generate-pdf');
const moveUpBtn = document.getElementById('move-up');
const moveDownBtn = document.getElementById('move-down');
const removeItemBtn = document.getElementById('remove-item');
const selectFileBtn = document.getElementById('select-file-btn');
const clearAllBtn = document.getElementById('clear-all');

// 初始化
function init() {
    // 添加事件监听器
    fileInput.addEventListener('change', handleFileSelect);
    
    // 拖放功能
    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.classList.add('dragover');
    });
    
    dropArea.addEventListener('dragleave', () => {
        dropArea.classList.remove('dragover');
    });
    
    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.classList.remove('dragover');
        
        if (e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    });
    
    // 点击选择图片按钮
    selectFileBtn.addEventListener('click', (e) => {
        e.preventDefault(); // 阻止默认行为
        e.stopPropagation(); // 阻止冒泡到dropArea
        fileInput.click();
    });
    
    // 按钮事件
    moveUpBtn.addEventListener('click', moveImageUp);
    moveDownBtn.addEventListener('click', moveImageDown);
    removeItemBtn.addEventListener('click', removeSelectedImage);
    clearAllBtn.addEventListener('click', clearAllImages);
    generateBtn.addEventListener('click', generatePDF);
    
    // PDF名称输入监听
    pdfNameInput.addEventListener('input', updateGenerateButton);
    
    // 监听滚动事件，使用虚拟列表
    previewList.addEventListener('scroll', debounce(() => {
        requestAnimationFrame(() => {
            updateVisibleThumbnails();
            updateVirtualList();
        });
    }, 50));
    
    // 初始化Worker
    if (window.Worker) {
        pdfWorker = new Worker('js/pdf-worker.js');
    }
    
    // 定期清理内存
    setInterval(releaseUnusedResources, 30000); // 每30秒清理一次
}

// 处理文件选择
function handleFileSelect(e) {
    handleFiles(e.target.files);
    
    // 重置文件输入框的值，允许再次选择相同文件
    e.target.value = '';
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

// 处理文件
function handleFiles(files) {
    const validFiles = Array.from(files).filter(file => {
        const type = file.type.toLowerCase();
        return type === 'image/jpeg' || type === 'image/jpg' || type === 'image/png';
    });
    
    if (validFiles.length === 0) return;
    
    // 如果图片数量很多，分批处理
    if (validFiles.length > 20) {
        showLoading('处理图片中...');
        
        // 分批添加图片
        const addImagesBatch = async (images, startIndex) => {
            const batchSize = 10;
            const endIndex = Math.min(startIndex + batchSize, images.length);
            const batch = images.slice(startIndex, endIndex);
            
            // 添加这一批
            imageFiles = [...imageFiles, ...batch];
            
            // 更新列表（仅添加新的批次）
            appendImageBatchToList(batch, imageFiles.length - batch.length);
            
            // 更新进度
            updateLoadingProgress((endIndex / images.length) * 100);
            
            // 如果还有更多批次，继续处理
            if (endIndex < images.length) {
                // 使用setTimeout让UI有时间更新
                setTimeout(() => {
                    addImagesBatch(images, endIndex);
                }, 50);
            } else {
                hideLoading();
                // 确保选中至少一个图片
                if (selectedIndex === -1 && imageFiles.length > 0) {
                    selectImage(0);
                }
                // 更新生成按钮状态
                updateGenerateButton();
            }
        };
        
        // 开始批处理
        addImagesBatch(validFiles, 0);
    } else {
        // 图片数量较少，直接处理
        imageFiles = [...imageFiles, ...validFiles];
        updateImageList();
        updateGenerateButton();
    }
}

// 仅添加一批图片到列表
function appendImageBatchToList(batch, startIndex) {
    batch.forEach((file, index) => {
        const listItem = document.createElement('li');
        const actualIndex = startIndex + index;
        listItem.dataset.index = actualIndex;
        
        // 创建缩略图
        const thumbnail = document.createElement('img');
        thumbnail.classList.add('thumbnail');
        thumbnail.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjZjBmMGYwIiAvPjwvc3ZnPg==';
        
        // 异步创建实际缩略图
        createThumbnail(file, actualIndex);
        
        // 创建文件名
        const fileName = document.createElement('span');
        fileName.textContent = file.name;
        
        // 添加到列表项
        listItem.appendChild(thumbnail);
        listItem.appendChild(fileName);
        
        // 点击选择图片
        listItem.addEventListener('click', () => {
            selectImage(actualIndex);
        });
        
        previewList.appendChild(listItem);
    });
}

// 更新图片列表
function updateImageList() {
    previewList.innerHTML = '';
    
    // 只有在有图片的情况下才处理
    if (imageFiles.length === 0) {
        return;
    }
    
    // 只渲染可视区域的图片项
    const itemHeight = 60; // 每个列表项的高度
    const visibleCount = Math.ceil(previewList.clientHeight / itemHeight); // 可见项数量
    const bufferCount = 5; // 额外的缓冲项数量，增加缓冲区以避免频繁重绘
    
    // 计算开始和结束索引，增加缓冲区
    const start = Math.max(0, Math.floor(previewList.scrollTop / itemHeight) - bufferCount);
    const end = Math.min(imageFiles.length, start + visibleCount + 2 * bufferCount); // 加入更多缓冲区
    
    // 创建占位元素保持滚动条正确高度
    const spacerHeight = start * itemHeight;
    const bottomSpacerHeight = (imageFiles.length - end) * itemHeight;
    
    if (spacerHeight > 0) {
        const topSpacer = document.createElement('li');
        topSpacer.className = 'placeholder';
        topSpacer.style.height = `${spacerHeight}px`;
        topSpacer.style.padding = '0';
        previewList.appendChild(topSpacer);
    }
    
    // 只渲染可见区域附近的图片
    for (let i = start; i < end; i++) {
        if (i >= imageFiles.length) break; // 安全检查
        
        const file = imageFiles[i];
        if (!file) continue; // 安全检查
        
        const listItem = document.createElement('li');
        listItem.dataset.index = i;
        
        // 创建缩略图
        const thumbnail = document.createElement('img');
        thumbnail.classList.add('thumbnail');
        
        // 尝试使用缓存的缩略图
        if (thumbnailCache[i]) {
            thumbnail.src = thumbnailCache[i];
        } else {
            thumbnail.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjZjBmMGYwIiAvPjwvc3ZnPg==';
            // 异步生成实际缩略图
            createThumbnail(file, i);
        }
        
        // 创建文件名
        const fileName = document.createElement('span');
        fileName.textContent = file.name;
        fileName.title = file.name; // 添加悬停提示，方便查看完整文件名
        
        // 添加到列表项
        listItem.appendChild(thumbnail);
        listItem.appendChild(fileName);
        
        // 如果是当前选中项，添加选中样式
        if (i === selectedIndex) {
            listItem.classList.add('selected');
        }
        
        // 点击选择图片
        listItem.addEventListener('click', () => {
            selectImage(i);
        });
        
        previewList.appendChild(listItem);
    }
    
    if (bottomSpacerHeight > 0) {
        const bottomSpacer = document.createElement('li');
        bottomSpacer.className = 'placeholder';
        bottomSpacer.style.height = `${bottomSpacerHeight}px`;
        bottomSpacer.style.padding = '0';
        previewList.appendChild(bottomSpacer);
    }
    
    // 如果有图片，确保选择状态正确
    if (imageFiles.length > 0) {
        if (selectedIndex === -1) {
            // 首次添加图片，选中第一个
            selectImage(0);
        } else if (selectedIndex >= imageFiles.length) {
            // 如果选中索引超出范围，选择最后一个
            selectImage(imageFiles.length - 1);
        } else {
            // 确保选中项可见
            ensureItemVisible(selectedIndex);
        }
    } else {
        // 没有图片时清空选择
        selectImage(-1);
    }
}

// 选择图片
function selectImage(index) {
    // 移除之前的选择
    const selectedItems = previewList.querySelectorAll('li.selected');
    selectedItems.forEach(item => item.classList.remove('selected'));
    
    // 设置新选择
    selectedIndex = index;
    if (index >= 0 && index < imageFiles.length) {
        // 查找对应的列表项
        const selectedItem = previewList.querySelector(`li[data-index="${index}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }
        
        // 更新大图预览
        const file = imageFiles[index];
        if (file) {
            // 使用原始文件生成预览图
            selectedImagePreview.src = URL.createObjectURL(file);
            selectedImagePreview.style.display = 'block';
        }
        
        // 启用控制按钮
        moveUpBtn.disabled = index === 0;
        moveDownBtn.disabled = index === imageFiles.length - 1;
        removeItemBtn.disabled = false;
    } else {
        // 没有选择时清空预览
        selectedImagePreview.src = '';
        selectedImagePreview.style.display = 'none';
        
        // 禁用控制按钮
        moveUpBtn.disabled = true;
        moveDownBtn.disabled = true;
        removeItemBtn.disabled = true;
    }
}

// 上移图片
function moveImageUp() {
    if (selectedIndex <= 0 || selectedIndex >= imageFiles.length) return;
    
    // 交换位置
    [imageFiles[selectedIndex - 1], imageFiles[selectedIndex]] = 
    [imageFiles[selectedIndex], imageFiles[selectedIndex - 1]];

    // 交换缓存的缩略图
    const tempThumb = thumbnailCache[selectedIndex - 1];
    thumbnailCache[selectedIndex - 1] = thumbnailCache[selectedIndex];
    thumbnailCache[selectedIndex] = tempThumb;
    
    // 保存当前滚动位置
    const currentScrollTop = previewList.scrollTop;
    
    // 选择移动后的项
    selectImage(selectedIndex - 1);
    
    // 恢复滚动位置
    previewList.scrollTop = currentScrollTop;
    
    // 强制更新虚拟列表，确保显示正确
    requestAnimationFrame(() => {
        updateVirtualList();
    });
}

// 下移图片
function moveImageDown() {
    if (selectedIndex < 0 || selectedIndex >= imageFiles.length - 1) return;
    
    // 交换位置
    [imageFiles[selectedIndex], imageFiles[selectedIndex + 1]] = 
    [imageFiles[selectedIndex + 1], imageFiles[selectedIndex]];
    
    // 交换缓存的缩略图
    const tempThumb = thumbnailCache[selectedIndex];
    thumbnailCache[selectedIndex] = thumbnailCache[selectedIndex + 1];
    thumbnailCache[selectedIndex + 1] = tempThumb;
    
    // 保存当前滚动位置
    const currentScrollTop = previewList.scrollTop;
    
    // 选择移动后的项
    selectImage(selectedIndex + 1);
    
    // 恢复滚动位置
    previewList.scrollTop = currentScrollTop;
    
    // 强制更新虚拟列表，确保显示正确
    requestAnimationFrame(() => {
        updateVirtualList();
    });
}

// 确保指定索引的项在可视区域内
function ensureItemVisible(index) {
    const itemHeight = 60; // 每个列表项的高度
    const containerHeight = previewList.clientHeight;
    const itemTop = index * itemHeight;
    const itemBottom = (index + 1) * itemHeight;
    
    // 如果项在可视区域上方，向上滚动
    if (itemTop < previewList.scrollTop) {
        previewList.scrollTop = itemTop;
    }
    // 如果项在可视区域下方，向下滚动
    else if (itemBottom > previewList.scrollTop + containerHeight) {
        previewList.scrollTop = itemBottom - containerHeight;
    }
}

// 删除选中图片
function removeSelectedImage() {
    if (selectedIndex < 0 || selectedIndex >= imageFiles.length) return;
    
    // 保存当前滚动位置
    const currentScrollTop = previewList.scrollTop;
    
    // 删除图片
    imageFiles.splice(selectedIndex, 1);
    
    // 重新调整缩略图缓存索引
    const newCache = {};
    for (let i = 0; i < selectedIndex; i++) {
        if (thumbnailCache[i]) {
            newCache[i] = thumbnailCache[i];
        }
    }
    
    // 所有后面的项向前移动
    for (let i = selectedIndex; i < imageFiles.length; i++) {
        if (thumbnailCache[i + 1]) {
            newCache[i] = thumbnailCache[i + 1];
        }
    }
    
    // 更新缩略图缓存
    thumbnailCache = newCache;
    
    // 选择新的项
    if (imageFiles.length === 0) {
        selectImage(-1);
    } else if (selectedIndex >= imageFiles.length) {
        selectImage(imageFiles.length - 1);
    } else {
        selectImage(selectedIndex);
    }
    
    // 恢复滚动位置
    previewList.scrollTop = currentScrollTop;
    
    // 强制更新虚拟列表，确保显示正确
    requestAnimationFrame(() => {
        updateVirtualList();
    });
    
    // 更新生成按钮状态
    updateGenerateButton();
}

// 更新生成按钮状态
function updateGenerateButton() {
    generateBtn.disabled = imageFiles.length === 0 || !pdfNameInput.value.trim();
}

// 生成PDF
async function generatePDF() {
    if (imageFiles.length === 0 || !pdfNameInput.value.trim()) return;
    
    // 显示加载提示
    showLoading('生成PDF中，请稍候...');
    
    // 获取PDF名称
    const pdfName = pdfNameInput.value.trim();
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const fileName = `${pdfName} ${today}.pdf`;
    
    try {
        // 使用Web Worker进行处理
        if (window.Worker && pdfWorker) {
            // 设置worker消息处理函数
            pdfWorker.onmessage = function(e) {
                const data = e.data;
                
                if (data.type === 'progress') {
                    // 更新进度
                    updateLoadingProgress(data.progress);
                } else if (data.type === 'complete') {
                    // 处理完成的PDF数据
                    const pdfData = data.data;
                    
                    // 创建blob并下载
                    const blob = new Blob([pdfData], {type: 'application/pdf'});
                    const url = URL.createObjectURL(blob);
                    
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = fileName;
                    a.click();
                    
                    URL.revokeObjectURL(url);
                    hideLoading();
                    alert(`PDF文件 "${fileName}" 已生成成功！`);
                } else if (data.type === 'error') {
                    // 处理错误
                    console.error('生成PDF时出错:', data.error);
                    hideLoading();
                    alert('生成PDF失败，请重试。');
                }
            };
            
            // 批量处理图片，每次处理一部分避免内存问题
            const batchSize = 5;
            const imageDataArray = [];
            
            for (let i = 0; i < imageFiles.length; i += batchSize) {
                showLoading(`处理图片 ${i+1}-${Math.min(i+batchSize, imageFiles.length)} / ${imageFiles.length}`);
                
                // 处理这一批次的图片
                const batch = imageFiles.slice(i, i + batchSize);
                const batchData = await Promise.all(
                    batch.map(file => getResizedImageDataUrl(file))
                );
                
                // 添加到结果数组
                imageDataArray.push(...batchData);
                
                // 更新整体进度
                updateLoadingProgress(Math.min(100, (i + batchSize) / imageFiles.length * 50)); // 图片处理占50%进度
            }
            
            showLoading('创建PDF文件...');
            
            // 发送所有图片数据到Worker
            pdfWorker.postMessage({
                imageData: imageDataArray,
                filename: fileName
            });
        } else {
            // 不支持Worker时的回退方案
            await generatePDFDirectly(fileName);
        }
    } catch (error) {
        console.error('生成PDF时出错:', error);
        hideLoading();
        alert('生成PDF失败，请重试。');
    }
}

// 不使用Worker的PDF生成（回退方案）
async function generatePDFDirectly(fileName) {
    try {
        // 创建PDF文档
        const pdf = new jsPDF({
            orientation: 'portrait',
            unit: 'mm'
        });
        
        let isFirstPage = true;
        
        // 添加所有图片到PDF
        for (let i = 0; i < imageFiles.length; i++) {
            updateLoadingProgress(Math.round((i + 1) / imageFiles.length * 100));
            
            // 获取处理后的图片
            const imgData = await getResizedImageDataUrl(imageFiles[i]);
            
            // 创建临时图片获取尺寸
            const img = new Image();
            
            // 等待图片加载完成
            await new Promise((resolve) => {
                img.onload = resolve;
                img.src = imgData;
            });
            
            // 计算图片尺寸，适应页面
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            
            let imgWidth = img.width;
            let imgHeight = img.height;
            
            // 缩放图片以适应页面
            if (imgWidth > pageWidth || imgHeight > pageHeight) {
                const ratio = Math.min(pageWidth / imgWidth, pageHeight / imgHeight);
                imgWidth *= ratio;
                imgHeight *= ratio;
            }
            
            // 添加新页（除了第一页）
            if (!isFirstPage) {
                pdf.addPage();
            } else {
                isFirstPage = false;
            }
            
            // 居中图片
            const x = (pageWidth - imgWidth) / 2;
            const y = (pageHeight - imgHeight) / 2;
            
            // 添加图片到PDF
            pdf.addImage(imgData, 'JPEG', x, y, imgWidth, imgHeight);
        }
        
        // 保存PDF
        pdf.save(fileName);
        
        hideLoading();
        alert(`PDF文件 "${fileName}" 已生成成功！`);
    } catch (error) {
        throw error;
    }
}

// 调整图片大小，返回DataURL
function getResizedImageDataUrl(file, maxWidth = 1800) {
    return new Promise((resolve) => {
        const img = new Image();
        const url = URL.createObjectURL(file);
        
        img.onload = () => {
            // 如果图片尺寸很小，直接使用原图
            if (img.width <= maxWidth) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    resolve(e.target.result);
                };
                reader.readAsDataURL(file);
                URL.revokeObjectURL(url);
                return;
            }
            
            // 计算缩放比例
            const ratio = maxWidth / img.width;
            const width = maxWidth;
            const height = img.height * ratio;
            
            // 使用canvas调整图片大小
            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);
            
            // 适当压缩图片质量
            const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
            URL.revokeObjectURL(url);
            resolve(dataUrl);
        };
        
        img.src = url;
    });
}

// 创建优化的缩略图
function createThumbnail(file, index) {
    // 如果已经有缓存，直接返回
    if (thumbnailCache[index]) {
        return thumbnailCache[index];
    }
    
    // 创建临时canvas生成缩略图
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 40;  // 缩略图宽度
    canvas.height = 40; // 缩略图高度
    
    const img = new Image();
    const url = URL.createObjectURL(file);
    
    img.onload = () => {
        // 计算保持比例的缩略图尺寸
        const ratio = Math.min(canvas.width / img.width, canvas.height / img.height);
        const width = img.width * ratio;
        const height = img.height * ratio;
        const x = (canvas.width - width) / 2;
        const y = (canvas.height - height) / 2;
        
        // 清空画布并绘制图片
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, x, y, width, height);
        
        // 转换为DataURL并缓存
        thumbnailCache[index] = canvas.toDataURL('image/jpeg', 0.5);
        
        // 更新列表中的图片
        const thumbnailElement = document.querySelector(`li[data-index="${index}"] .thumbnail`);
        if (thumbnailElement) {
            thumbnailElement.src = thumbnailCache[index];
        }
        
        // 释放原始URL
        URL.revokeObjectURL(url);
    };
    
    img.src = url;
    
    // 返回一个占位图，等实际缩略图加载完成
    return 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjZjBmMGYwIiAvPjwvc3ZnPg==';
}

// 更新虚拟列表
function updateVirtualList() {
    if (imageFiles.length === 0) return; // 没有图片时不处理
    
    // 当前可见区域的起始和结束索引
    const itemHeight = 60;
    const visibleHeight = previewList.clientHeight;
    const startIdx = Math.max(0, Math.floor(previewList.scrollTop / itemHeight) - 5); // 增加上方缓冲区
    const endIdx = Math.min(
        imageFiles.length - 1, 
        Math.floor((previewList.scrollTop + visibleHeight) / itemHeight) + 5 // 增加下方缓冲区
    );
    
    // 如果没有足够的项目来填充视口，则显示所有项目
    if (endIdx - startIdx + 1 < Math.ceil(visibleHeight / itemHeight) || imageFiles.length <= 20) {
        // 有限数量的项目，直接重新渲染所有
        updateImageList();
        return;
    }
    
    // 清空列表
    previewList.innerHTML = '';
    
    // 创建顶部填充元素
    if (startIdx > 0) {
        const topSpacer = document.createElement('li');
        topSpacer.className = 'placeholder';
        topSpacer.style.height = `${startIdx * itemHeight}px`;
        topSpacer.style.padding = '0';
        previewList.appendChild(topSpacer);
    }
    
    // 渲染可见区域内的项
    for (let i = startIdx; i <= endIdx; i++) {
        if (i >= imageFiles.length) break;
        
        const file = imageFiles[i];
        if (!file) continue;
        
        const listItem = document.createElement('li');
        listItem.dataset.index = i;
        
        // 创建缩略图
        const thumbnail = document.createElement('img');
        thumbnail.classList.add('thumbnail');
        
        // 尝试使用缓存的缩略图
        if (thumbnailCache[i]) {
            thumbnail.src = thumbnailCache[i];
        } else {
            thumbnail.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjZjBmMGYwIiAvPjwvc3ZnPg==';
            // 异步生成实际缩略图
            createThumbnail(file, i);
        }
        
        // 创建文件名
        const fileName = document.createElement('span');
        fileName.textContent = file.name;
        fileName.title = file.name;
        
        // 添加到列表项
        listItem.appendChild(thumbnail);
        listItem.appendChild(fileName);
        
        // 如果是当前选中项，添加选中样式
        if (i === selectedIndex) {
            listItem.classList.add('selected');
        }
        
        // 点击选择图片
        listItem.addEventListener('click', () => {
            selectImage(i);
        });
        
        previewList.appendChild(listItem);
    }
    
    // 创建底部填充元素
    if (endIdx < imageFiles.length - 1) {
        const bottomSpacer = document.createElement('li');
        bottomSpacer.className = 'placeholder';
        bottomSpacer.style.height = `${(imageFiles.length - endIdx - 1) * itemHeight}px`;
        bottomSpacer.style.padding = '0';
        previewList.appendChild(bottomSpacer);
    }
}

// 更新可见缩略图
function updateVisibleThumbnails() {
    const visibleItems = getVisibleItems();
    
    visibleItems.forEach(item => {
        const index = parseInt(item.dataset.index);
        if (isNaN(index)) return;
        
        const thumbnailElement = item.querySelector('.thumbnail');
        if (!thumbnailElement) return;
        
        // 如果已经有缓存图像，使用缓存图像
        if (thumbnailCache[index]) {
            thumbnailElement.src = thumbnailCache[index];
        } 
        // 否则，创建新的缩略图
        else if (index >= 0 && index < imageFiles.length) {
            createThumbnail(imageFiles[index], index);
        }
    });
}

// 获取可见列表项
function getVisibleItems() {
    const items = Array.from(previewList.querySelectorAll('li:not(.placeholder)'));
    const containerRect = previewList.getBoundingClientRect();
    
    return items.filter(item => {
        const rect = item.getBoundingClientRect();
        return rect.bottom > containerRect.top && rect.top < containerRect.bottom;
    });
}

// 内存优化：释放不必要的资源
function releaseUnusedResources() {
    // 释放未显示的缩略图
    const visibleItems = getVisibleItems();
    const visibleIndices = new Set();
    
    visibleItems.forEach(item => {
        if (item.dataset.index) {
            visibleIndices.add(parseInt(item.dataset.index));
        }
    });
    
    // 仅保留可见项和选中项的缩略图
    Object.keys(thumbnailCache).forEach(key => {
        const index = parseInt(key);
        if (!visibleIndices.has(index) && index !== selectedIndex) {
            delete thumbnailCache[key];
        }
    });
}

// 显示加载提示
function showLoading(message) {
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="loading-container">
            <div class="spinner"></div>
            <p id="loading-message">${message}</p>
            <progress id="loading-progress" value="0" max="100"></progress>
        </div>
    `;
    document.body.appendChild(loadingOverlay);
}

// 更新进度
function updateLoadingProgress(percent) {
    const progress = document.getElementById('loading-progress');
    if (progress) {
        progress.value = percent;
    }
}

// 隐藏加载提示
function hideLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.remove();
    }
}

// 清空所有图片
function clearAllImages() {
    if (imageFiles.length === 0) return;
    
    // 确认是否清空
    if (confirm('确定要清空所有图片吗？')) {
        // 清空图片数组
        imageFiles = [];
        
        // 清空缩略图缓存
        thumbnailCache = {};
        
        // 清空预览和选择
        selectImage(-1);
        
        // 更新列表
        updateImageList();
        
        // 更新生成按钮状态
        updateGenerateButton();
    }
}

// 初始化应用
window.addEventListener('DOMContentLoaded', init);
