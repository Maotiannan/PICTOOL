import os
import datetime
import img2pdf
from tkinter import Tk, Label, Entry, Button, filedialog, messagebox, Frame, Menu
from PIL import Image, ImageTk
from tkinter import ttk

class ImageToPdfConverter(Tk):
    def __init__(self):
        super().__init__()
        
        self.title("图片生成PDF工具")
        self.geometry("600x500")
        
        # 创建主框架
        self.main_frame = Frame(self)
        self.main_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        # 文件选择区域
        self.folder_frame = Frame(self.main_frame)
        self.folder_frame.pack(fill='x', pady=5)
        
        Label(self.folder_frame, text="选择图片文件夹:").pack(side='left')
        self.folder_entry = Entry(self.folder_frame, width=40)
        self.folder_entry.pack(side='left', padx=5)
        Button(self.folder_frame, text="浏览...", command=self.select_folder).pack(side='left')
        
        # PDF名称区域
        self.name_frame = Frame(self.main_frame)
        self.name_frame.pack(fill='x', pady=5)
        
        Label(self.name_frame, text="输入 PDF 文件名:").pack(side='left')
        self.pdf_name_entry = Entry(self.name_frame, width=40)
        self.pdf_name_entry.pack(side='left', padx=5)
        
        # 预览区域
        self.preview_frame = Frame(self.main_frame)
        self.preview_frame.pack(fill='both', expand=True, pady=5)
        
        # 创建一个固定高度的预览区域框架
        self.list_frame = Frame(self.preview_frame, height=200)
        self.list_frame.pack(fill='both', expand=True)
        self.list_frame.pack_propagate(False)
        
        # 添加上下移动按钮到list_frame中
        self.button_frame = Frame(self.list_frame)
        self.button_frame.pack(side='left', fill='y', padx=5)
        Button(self.button_frame, text="↑", command=self.move_up).pack(pady=2)
        Button(self.button_frame, text="↓", command=self.move_down).pack(pady=2)
        
        # 创建预览列表到list_frame中
        self.preview_list = ttk.Treeview(self.list_frame, columns=('文件名',), show='headings')
        self.preview_list.heading('文件名', text='图片文件')
        self.preview_list.pack(side='left', fill='both', expand=True)
        
        # 添加滚动条到list_frame中
        scrollbar = ttk.Scrollbar(self.list_frame, orient='vertical', command=self.preview_list.yview)
        scrollbar.pack(side='right', fill='y')
        self.preview_list.configure(yscrollcommand=scrollbar.set)
        
        # 创建一个固定高度的图片预览框架
        self.preview_image_frame = Frame(self.preview_frame, height=150)
        self.preview_image_frame.pack(fill='x', pady=5)
        self.preview_image_frame.pack_propagate(False)
        
        # 预览图片区域
        self.image_preview = Label(self.preview_image_frame)
        self.image_preview.pack(expand=True)
        
        # 生成按钮
        self.generate_button = Button(self.main_frame, text="生成 PDF", command=self.create_pdf)
        self.generate_button.pack(pady=10)
        
        # 绑定预览列表选择事件
        self.preview_list.bind('<<TreeviewSelect>>', self.show_preview)
        
        self.current_images = []
        
        # 创建右键菜单
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="删除", command=self.remove_selected)
        self.preview_list.bind("<Button-3>", self.show_context_menu)
    
    def move_up(self):
        """将选中项目向上移动"""
        selection = self.preview_list.selection()
        if not selection:
            return
            
        item = selection[0]
        idx = self.preview_list.index(item)
        if idx > 0:
            # 更新列表显示
            prev = self.preview_list.prev(item)
            self.preview_list.move(item, '', idx - 1)
            # 更新图片列表
            self.current_images[idx], self.current_images[idx-1] = \
                self.current_images[idx-1], self.current_images[idx]
            # 保持选中状态
            self.preview_list.selection_set(item)
    
    def move_down(self):
        """将选中项目向下移动"""
        selection = self.preview_list.selection()
        if not selection:
            return
            
        item = selection[0]
        idx = self.preview_list.index(item)
        if idx < len(self.current_images) - 1:
            # 更新列表显示
            next = self.preview_list.next(item)
            self.preview_list.move(item, '', idx + 1)
            # 更新图片列表
            self.current_images[idx], self.current_images[idx+1] = \
                self.current_images[idx+1], self.current_images[idx]
            # 保持选中状态
            self.preview_list.selection_set(item)
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        item = self.preview_list.identify_row(event.y)
        if item:
            self.preview_list.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def remove_selected(self):
        """从列表中删除选中项"""
        selection = self.preview_list.selection()
        if not selection:
            return
            
        item = selection[0]
        idx = self.preview_list.index(item)
        # 从列表和数据中删除
        self.preview_list.delete(item)
        del self.current_images[idx]
        
        # 如果还有其他项目，选中下一个
        if self.preview_list.get_children():
            next_idx = min(idx, len(self.current_images) - 1)
            next_item = self.preview_list.get_children()[next_idx]
            self.preview_list.selection_set(next_item)
            self.show_preview(None)
    
    def select_folder(self):
        """选择图片文件夹"""
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.folder_entry.delete(0, 'end')
            self.folder_entry.insert(0, folder_path)
            self.update_preview_list(folder_path)
    
    def update_preview_list(self, folder_path):
        """更新预览列表"""
        self.preview_list.delete(*self.preview_list.get_children())
        self.current_images = []
        
        for f in os.listdir(folder_path):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = os.path.join(folder_path, f)
                self.current_images.append(full_path)
                self.preview_list.insert('', 'end', values=(f,))
    
    def show_preview(self, event):
        """显示选中图片的预览"""
        selection = self.preview_list.selection()
        if not selection:
            return
            
        index = self.preview_list.index(selection[0])
        if index < len(self.current_images):
            try:
                # 加载并调整图片大小
                image = Image.open(self.current_images[index])
                # 计算缩放比例，限制预览大小
                max_size = (150, 150)
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                
                self.image_preview.configure(image=photo)
                self.image_preview.image = photo  # 保持引用
            except Exception as e:
                messagebox.showerror("错误", f"无法预览图片: {e}")
    
    def create_pdf(self):
        """从 GUI 获取输入并调用生成 PDF 的函数"""
        folder_path = self.folder_entry.get()
        pdf_name = self.pdf_name_entry.get()
        
        if not folder_path or not os.path.isdir(folder_path):
            messagebox.showwarning("警告", "请选择一个有效的文件夹。")
            return
            
        if not pdf_name:
            messagebox.showwarning("警告", "请输入 PDF 文件名。")
            return
            
        if not self.current_images:
            messagebox.showwarning("警告", "选择的文件夹中没有找到任何图片文件。")
            return
            
        try:
            # 设置输出路径和文件名
            today = datetime.datetime.now().strftime("%Y%m%d")
            pdf_file_name = f"{pdf_name} {today}.pdf"
            output_path = os.path.join(folder_path, pdf_file_name)
            
            # 使用 img2pdf 生成 PDF 文件，不压缩图片
            with open(output_path, "wb") as f:
                f.write(img2pdf.convert(self.current_images))
            
            messagebox.showinfo("完成", f"PDF 文件已生成！\n保存路径: {output_path}")
        except Exception as e:
            messagebox.showerror("错误", f"生成 PDF 失败: {e}")

if __name__ == "__main__":
    app = ImageToPdfConverter()
    app.mainloop()
