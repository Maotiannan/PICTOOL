--- START OF FILE README.md ---

批量图片加水印工具
这是一个使用 Python 和 Tkinter 编写的图形界面应用程序，可以方便地为指定文件夹中的所有图片批量添加文本水印。

主要功能
图形用户界面 (GUI)：操作直观，易于使用。

批量处理：自动处理指定文件夹内所有支持的图片文件。

支持格式：支持常见的图片格式，如 PNG, JPG, JPEG, BMP, GIF, WEBP。

自定义文本：可自由输入水印文字内容，支持中英文混合，并可通过 {exif_date} 占位符动态插入图片的拍摄日期。

自定义样式：

可设置水印字体大小。

可调整水印透明度 (0-100%)。

可通过调色板选择水印颜色。

可选择水印在图片上的位置（左上角、右上角、左下角、右下角、中心）。

可选 高对比度模式，程序自动选择与背景对比强烈的颜色（黑或白）。

多尺寸适配：可选功能，启用后程序会根据图片尺寸自动调整字体大小，以获得更和谐的视觉效果。

效果预览：在处理前可以预览水印在第一张图片上的效果。

进度显示：批量处理时显示进度条和当前处理的文件名。

运行时停止：在批量处理过程中，可以随时点击“停止处理”按钮中断任务。

自动保存：处理后的图片会自动保存在原文件夹下的 Watermarked_Images 子目录中，不覆盖原图。

设置记忆：可以保存当前的水印设置（文本、大小、颜色、位置等）到 settings.json 文件，下次启动时自动加载。

日志记录：运行过程和错误信息会记录到 GUI 界面的日志区域和控制台，方便排查问题。

完成后打开文件夹：处理完成后，可以选择直接打开包含结果的输出文件夹。

软件截图
(此处可以添加几张应用程序运行时的界面截图，展示主要功能区域，包括新增的'停止处理'按钮)

主界面截图

颜色选择器截图

预览效果截图 (可选)

获取与运行
方式一：使用预编译的可执行文件 (推荐)
如果开发者提供了针对您操作系统的预编译版本（例如 Windows 下的 .exe 文件），请直接下载该文件。

运行： 直接双击运行下载的可执行文件即可启动程序。这是最简单的方式，无需安装 Python 环境。

方式二：通过 Python 源代码运行
如果你熟悉 Python 环境，或者没有提供你操作系统的预编译版本，可以选择从源代码运行。

环境要求
Python 3.x

Pillow 库 (Python Imaging Library 的 Fork)

安装步骤
安装 Python: 如果你的系统中没有安装 Python 3，请先从 Python 官网 下载并安装。

获取源代码: 下载或克隆本项目的所有文件（watermark_app.py, settings.json (如果存在), README.md 等）到你的本地计算机。

安装 Pillow 库: 打开命令行终端（或 PowerShell），切换到包含源代码的目录，运行以下命令：

pip install Pillow
Use code with caution.
Bash
运行程序
在命令行终端中，确保你位于包含 watermark_app.py 文件的目录。

运行以下命令启动程序：

python watermark_app.py
Use code with caution.
Bash
构建可执行文件 (可选)
如果你想自己从源代码构建可执行文件，推荐使用 PyInstaller：

设置虚拟环境 (推荐):

# 在项目目录下
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
Use code with caution.
Bash
安装依赖:

pip install Pillow pyinstaller
Use code with caution.
Bash
运行 PyInstaller: (在包含 watermark_app.py 和 settings.json 的目录下)

# 基础命令 (生成单文件，包含设置文件):
# Windows (注意分隔符是分号 ;):
pyinstaller --windowed --onefile --name WatermarkTool --add-data "settings.json;." watermark_app.py
# macOS/Linux (注意分隔符是冒号 :):
pyinstaller --windowed --onefile --name WatermarkTool --add-data "settings.json:." watermark_app.py
Use code with caution.
Bash
--windowed: 创建无控制台窗口的 GUI 应用。

--onefile: 打包成单个可执行文件。

--name: 指定输出文件的名称。

--add-data: 将 settings.json 文件包含进包内。

打包后的程序位于 dist 文件夹下。

你可以根据需要添加 --icon=<图标路径> 等选项。请查阅 PyInstaller 文档获取更多信息。

注意: 打包过程必须在你想要运行程序的操作系统上进行（例如，在 Windows 上打包 Windows 程序）。

使用说明
启动应用：通过可执行文件或 python watermark_app.py 命令启动。

输入水印内容：在顶部的输入框中填写你想要添加的水印文字。可以使用 {exif_date} 占位符。点击旁边的 "?" 图标可查看说明。

设置样式：

输入合适的基础字体大小。

如果希望字体大小根据图片尺寸自动调整，请勾选 “多尺寸适配” 复选框。

输入 透明度 (0-100)。

点击 “选择颜色” 按钮选择颜色。

如果希望程序自动选择对比色，勾选 “高对比度模式”。

在 “选择水印位置” 下拉菜单中选择位置。

选择图片文件夹：点击 “选择文件夹” 按钮，选择包含待处理图片的文件夹。

(可选) 预览效果：点击 “预览水印” 按钮，查看在首张图片上的效果。

(可选) 保存设置：点击 “保存设置” 按钮，将当前配置保存到 settings.json。

开始处理：点击绿色的 “开始处理” 按钮。进度条和文本将显示进度。在处理过程中，你可以点击红色的 “停止处理” 按钮来中断任务。

处理完成：处理结束后（或被停止后），会弹出一个提示框告知处理结果（成功、跳过/失败、或已停止）。如果处理成功，可能会询问你是否要打开包含结果的 Watermarked_Images 输出文件夹。

配置文件 (settings.json)
当你点击“保存设置”时，或程序启动时自动加载（如果存在），使用的是程序运行目录下的 settings.json 文件。

如果你使用 PyInstaller 打包成单文件，该文件会被包含在可执行文件内部。

文件内容类似：

{
    "watermark_text": "你的水印文本 {exif_date}",
    "font_size": "50",
    "opacity": "80",
    "color": [255, 255, 0],
    "position": "右下角",
    "multi_size": "1", // "1" 勾选, "0" 未勾选
    "high_contrast": "0" // "1" 勾选, "0" 未勾选
}
Use code with caution.
Json
注意事项
字体支持：程序会尝试使用系统中常见的字体。如果系统缺少合适的字体（尤其是中文字体），水印可能无法正确显示。建议确保系统安装了支持中英文的 TrueType/OpenType 字体（如微软雅黑、思源黑体、SimSun 等）。

GIF 处理：对于 GIF 动态图片，程序仅处理第一帧并将其保存为静态 PNG 图片，以保留可能的透明度。动画效果会丢失。

错误处理：如果遇到无法处理的图片文件，程序会记录错误到日志区域和控制台，并在处理完当前图片后继续处理剩余文件（除非发生严重错误）。

故障排查
如果程序无法启动或运行中出现错误，请查看控制台输出或界面上的日志区域获取详细错误信息。

确保已正确安装 Pillow 库（如果从源代码运行）。

检查所选文件夹中的图片文件是否是支持的格式且没有损坏。

打包后的可执行文件（尤其是使用 --onefile 选项）有时可能被某些杀毒软件误报为病毒。这通常是由于打包方式引起的，可以尝试将程序添加到信任列表，或使用 PyInstaller 的 --onedir 模式打包（生成一个文件夹而不是单文件）。

--- END OF FILE README.md ---