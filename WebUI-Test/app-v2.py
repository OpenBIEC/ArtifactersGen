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

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# In-memory image storage
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
        # Find base images with the same prefix
        candidates = [f"{prefix} 肖形.png", f"{prefix} 写照.png"]
        base_images = [f for f in candidates if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], f))]
        if not base_images:
            return jsonify({'error': 'No base images found'}), 400
        # Randomly select a base image
        base_filename = random.choice(base_images)
        base_path = os.path.join(app.config['UPLOAD_FOLDER'], base_filename)
        # Load base image
        base_img = Image.open(base_path).convert('RGBA')
        width, height = base_img.size
        base_rgba = np.array(base_img)
        base_rgb = base_rgba[:, :, :3]
        base_alpha = base_rgba[:, :, 3]
        # Generate noise for RGB and alpha
        noise_rgb = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        noise_alpha = np.random.randint(0, 256, (height, width), dtype=np.uint8)
        # Denoising steps
        N = 5
        denoising_image_urls = []
        for k in range(N + 1):
            w = k / N
            # Compute current step RGB and alpha
            step_rgb = ((1 - w) * noise_rgb + w * base_rgb).astype(np.uint8)
            step_alpha = ((1 - w) * noise_alpha + w * base_alpha).astype(np.uint8)
            # Create RGBA image
            step_rgba = np.dstack((step_rgb, step_alpha))
            step_img = Image.fromarray(step_rgba, 'RGBA')
            # Flatten on white background
            background = Image.new('RGBA', (width, height), (255, 255, 255, 255))
            flattened = Image.alpha_composite(background, step_img).convert('RGB')
            # Save to memory
            img_io = io.BytesIO()
            flattened.save(img_io, format='PNG')
            img_io.seek(0)
            # Generate temporary URL
            temp_id = str(uuid.uuid4())
            memory_images[temp_id] = img_io
            denoising_image_urls.append(f"/images/temp/{temp_id}")
        # Original uploaded image URL
        original_url = f"/images/{filename}"
        return jsonify({'original': original_url, 'denoising_images': denoising_image_urls})

@app.route('/images/<filename>')
def get_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/images/temp/<temp_id>')
def get_temp_image(temp_id):
    if temp_id in memory_images:
        return send_file(memory_images[temp_id], mimetype='image/png')
    else:
        return jsonify({'error': 'Image not found'}), 404

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True)