from flask import Flask, request, jsonify
from deepface import DeepFace
import os
import cv2
import requests
import numpy as np
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)


# Konfigurasi folder dataset wajah dan hasil scan di Laravel
BASE_LARAVEL_STORAGE = os.path.abspath("../rekachain-web/storage/app/public")
DB_PATH = os.path.join(BASE_LARAVEL_STORAGE, "dataset_faces")
RESULT_FOLDER = os.path.join(BASE_LARAVEL_STORAGE, "result_scan_faces")

# Pastikan folder dataset_faces dan result_scan_faces ada
os.makedirs(DB_PATH, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = DB_PATH
LARAVEL_API_URL = "http://192.168.1.11:8000/scan-faces"

def save_face_image(image_path, name):
    # Baca gambar menggunakan OpenCV
    img = cv2.imread(image_path)

    if img is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        face_filename = f"{name}_{timestamp}.jpg"
        face_path = os.path.join(DB_PATH, name, face_filename)

        # Pastikan folder user ada
        os.makedirs(os.path.dirname(face_path), exist_ok=True)

        cv2.imwrite(face_path, img)
        return face_path
    return None

@app.route("/register", methods=["POST"])
def register():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    name = request.form.get("name")
    if not name:
        return jsonify({"error": "Name not provided"}), 400

    user_folder = os.path.join(DB_PATH, name)

    user_folder = os.path.join(DB_PATH, name)
    os.makedirs(user_folder, exist_ok=True)  # Pastikan folder user ada

    filename = secure_filename(file.filename)
    temp_file_path = os.path.join(DB_PATH, filename)
    file.save(temp_file_path)

    try:
        face_path = save_face_image(temp_file_path, name)
        
        if face_path:
            final_face_path = os.path.join(user_folder, os.path.basename(face_path))
            os.rename(face_path, final_face_path)

            return jsonify({
                "status": "success",
                "message": f"Face registered as {name}",
                "face_path": final_face_path
            }), 200
        else:
            return jsonify({"status": "failed", 
                            "message": "No face detected in the image"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        
@app.route("/recognize", methods=["POST"])
def recognize():
    print("Received request for recognition")
    if "file" not in request.files or "username" not in request.form:
        return jsonify({"error": "File and username are required"}), 400

    file = request.files["file"]
    username = request.form["username"]
    user_id  = request.form["id"]
    panel  = request.form["panel"]
    kpm  = request.form["kpm"]
    
    print(f"Received file: {file}, username: {username}, user_id: {user_id}, panel: {panel}, kpm: {kpm}")

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    user_dataset_path = os.path.join(DB_PATH, username)

    if not os.path.exists(user_dataset_path):
        return jsonify({"status": "2"}), 200

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    
    try:
        dataset_images = [os.path.join(user_dataset_path, img) for img in os.listdir(user_dataset_path)[:3]]
        print(f"Dataset images: {dataset_images}")

        for dataset_image in dataset_images:
            print(f"Comparing with: {dataset_image}")
            result = DeepFace.verify(img1_path=file_path, img2_path=dataset_image, model_name="Facenet")
            print(f"Result: {result}")

            if result["verified"]: 
                result_filename = f"{username}_{filename}"
                result_image_path = os.path.join(RESULT_FOLDER, result_filename)
                cv2.imwrite(result_image_path, cv2.imread(file_path))
                
                status = "SUKSES"
                send_data_to_laravel(user_id, result_filename, status, panel, kpm)
                
                return jsonify({"status": "1"}), 200 
            else:
                result_filename = f"{username}_{filename}"
                result_image_path = os.path.join(RESULT_FOLDER, result_filename)
                cv2.imwrite(result_image_path, cv2.imread(file_path))
                        
                status = "GAGAL"
                send_data_to_laravel(user_id, result_filename, status, panel, kpm)
                return jsonify({"status": "0"}), 200 

    except Exception as e:
        print(f"Error during face verification: {str(e)}") 
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            
def send_data_to_laravel(user_id, result_image_path, status, panel, kpm):
    """Fungsi untuk mengirim data ke Laravel"""
    data = {
        "user_id": user_id,
        "image_path": result_image_path if result_image_path else None,
        "status": status,
        "panel": panel,
        "kpm": kpm
    }
    
    headers = {
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        # Mengirim request POST ke Laravel API
        response = requests.post(LARAVEL_API_URL, data=data, headers=headers)
        print(f"Response from Laravel: {response.text}")
        if response.status_code == 201 :
            print("Data berhasil dikirim ke Laravel")
        else:
            print(f"Failed to send data to Laravel. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error while sending data to Laravel: {str(e)}")

if __name__ == "__main__":
    # app.run(host='192.168.72.7', port=5000,debug=True)
    app.run(host='192.168.1.11', port=5000,debug=True)
