#!/usr/bin/env python3
"""
简单的HTTP服务器，用于本地运行图片转GIF工具
使用方法：
1. 双击运行此脚本
2. 在浏览器中访问 http://localhost:8000
3. 按 Ctrl+C 停止服务器
"""

import http.server
import socketserver
import webbrowser
import os
import sys

# 设置端口
PORT = 8000

# 获取当前脚本所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)

# 创建HTTP服务器
Handler = http.server.SimpleHTTPRequestHandler

try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🚀 服务器启动成功！")
        print(f"📍 服务器地址: http://localhost:{PORT}")
        print(f"📁 服务器目录: {current_dir}")
        print(f"🎬 图片转GIF工具: http://localhost:{PORT}/index.html")
        print(f"🧪 测试页面: http://localhost:{PORT}/test.html")
        print(f"📴 离线版本: http://localhost:{PORT}/index-offline.html")
        print(f"\n按 Ctrl+C 停止服务器")
        
        # 自动打开浏览器
        try:
            webbrowser.open(f'http://localhost:{PORT}/index.html')
        except:
            pass
        
        # 启动服务器
        httpd.serve_forever()
        
except KeyboardInterrupt:
    print(f"\n👋 服务器已停止")
    sys.exit(0)
except OSError as e:
    if e.errno == 48:  # Address already in use
        print(f"❌ 端口 {PORT} 已被占用，请关闭其他程序或修改端口号")
    else:
        print(f"❌ 启动服务器时出错: {e}")
    sys.exit(1) 