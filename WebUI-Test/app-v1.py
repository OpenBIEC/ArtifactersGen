from flask import Flask, request, jsonify, send_file, send_from_directory
import os
import random
from PIL import Image
import numpy as np
import io
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 确保上传文件夹存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 内存中的图像存储
memory_images = {}

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        prefix = os.path.splitext(filename)[0]
        # 查找同前缀的基底图像
        candidates = [f"{prefix} 肖形.png", f"{prefix} 写照.png"]
        base_images = [f for f in candidates if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], f))]
        if not base_images:
            return jsonify({'error': 'No base images found'}), 400
        # 随机选择一个基底图像
        base_filename = random.choice(base_images)
        base_path = os.path.join(app.config['UPLOAD_FOLDER'], base_filename)
        # 加载基底图像
        base_img = Image.open(base_path).convert('RGBA')
        width, height = base_img.size
        base_rgb = np.array(base_img)[:,:,:3]
        base_alpha = base_img.split()[3]
        # 生成噪声 RGB
        noise_rgb = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        # 去噪步骤数
        N = 5
        denoising_image_urls = []
        for k in range(N + 1):
            if k == 0:
                step_rgb = noise_rgb
            else:
                w = k / N
                step_rgb = (w * base_rgb + (1 - w) * noise_rgb).astype(np.uint8)
            # 创建 RGBA 图像
            step_img = Image.fromarray(step_rgb, 'RGB').convert('RGBA')
            step_img.putalpha(base_alpha)
            # 在白色背景上展平
            background = Image.new('RGBA', (width, height), (255, 255, 255, 255))
            flattened = Image.alpha_composite(background, step_img).convert('RGB')
            # 保存到内存
            img_io = io.BytesIO()
            flattened.save(img_io, format='PNG')
            img_io.seek(0)
            # 生成临时 URL
            temp_id = str(uuid.uuid4())
            memory_images[temp_id] = img_io
            denoising_image_urls.append(f"/images/temp/{temp_id}")
        # 原始上传图像的 URL
        original_url = f"/images/{filename}"
        return jsonify({'original': original_url, 'denoising_images': denoising_image_urls})

@app.route('/images/<filename>')
def get_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/images/temp/<temp_id>')
def get_temp_image(temp_id):
    if temp_id in memory_images:
        return send_file(memory_images[temp_id], mimetype='image/png')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
