// 导入jsPDF库
importScripts('https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js');

// 监听消息
self.onmessage = function(e) {
    const { imageData, filename } = e.data;
    
    try {
        // 创建PDF
        const { jsPDF } = self.jspdf;
        const pdf = new jsPDF({
            orientation: 'portrait',
            unit: 'mm'
        });
        
        let isFirstPage = true;
        
        // 添加图片到PDF
        for (let i = 0; i < imageData.length; i++) {
            const imgData = imageData[i];
            
            // 创建临时图片获取尺寸
            const img = new Image();
            
            // 加载图片并获取尺寸
            img.src = imgData;
            
            // 同步获取图片尺寸（Web Worker中可以同步等待）
            const imgWidth = img.width;
            const imgHeight = img.height;
            
            // 计算图片尺寸，适应页面
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            
            let width = imgWidth;
            let height = imgHeight;
            
            // 缩放图片以适应页面
            if (width > pageWidth || height > pageHeight) {
                const ratio = Math.min(pageWidth / width, pageHeight / height);
                width *= ratio;
                height *= ratio;
            }
            
            // 添加新页（除了第一页）
            if (!isFirstPage) {
                pdf.addPage();
            } else {
                isFirstPage = false;
            }
            
            // 居中图片
            const x = (pageWidth - width) / 2;
            const y = (pageHeight - height) / 2;
            
            // 添加图片到PDF
            pdf.addImage(imgData, 'JPEG', x, y, width, height);
            
            // 报告进度
            self.postMessage({
                type: 'progress',
                progress: Math.round((i + 1) / imageData.length * 100)
            });
        }
        
        // 获取PDF数据
        const pdfData = pdf.output('arraybuffer');
        
        // 发送完成消息
        self.postMessage({
            type: 'complete',
            data: pdfData
        });
    } catch (error) {
        // 发送错误消息
        self.postMessage({
            type: 'error',
            error: error.message || 'PDF生成失败'
        });
    }
}; 