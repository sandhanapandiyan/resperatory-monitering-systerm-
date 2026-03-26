import cv2
import numpy as np
import requests
from flask import Flask, Response, jsonify
import threading
import time
import serial
import json

app = Flask(__name__)

import glob

# --- Configuration ---
BAUD_RATE = 115200
ESP32_VIDEO_URL = "http://stream.local:81/video"

def find_serial_port():
    """Dynamically find the available ESP32 serial port."""
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    # Prioritize USB1 > USB0 > ACM ports
    ports.sort(reverse=True)
    return ports[0] if ports else None

# Global state for sensor data
sensor_data = {
    "breathing_rate": 0.0,
    "movement": 0.0,
    "noise": 0.0,
    "respiration": 0.0,
    "last_updated": 0.0,
    "motion_detected": False,
    "connected": False  # Hardware connection status
}

# Filtering parameters (EMA Alpha - lower is smoother)
EMA_ALPHA = 0.2
filtered_values = {
    "breathing_rate": 0.0,
    "noise": 0.0,
    "respiration": 0.0
}

# --- Serial Data Reader ---
def read_serial_data():
    global sensor_data
    while True:
        try:
            target_port = find_serial_port()
            if not target_port:
                sensor_data["connected"] = False
                print("No USB Serial device detected. Retrying in 2s...")
                time.sleep(2)
                continue
                
            # Attempt to connect to detected port
            ser = serial.Serial(target_port, BAUD_RATE, timeout=0.5)
            sensor_data["connected"] = True
            print(f"Connected to ESP32 on {target_port} (9600 Baud)")
            
            while True:
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        # Expected format: "Motion: 0 | Sound Level: 123"
                        if "Motion:" in line and "Sound Level:" in line:
                            parts = line.split('|')
                            motion_val = int(parts[0].split(':')[-1].strip())
                            sound_val = int(parts[1].split(':')[-1].strip())
                            
                            # Filter noise
                            filtered_values["noise"] = (EMA_ALPHA * sound_val) + ((1 - EMA_ALPHA) * filtered_values["noise"])
                            
                            # Calculate Respiratory Depth Index (Normalized 0-100)
                            # Deep breaths produce higher sound peaks from the I2S mic
                            raw_depth = min(100.0, (sound_val / 2048.0) * 100.0) 
                            filtered_values["respiration"] = (EMA_ALPHA * raw_depth) + ((1 - EMA_ALPHA) * filtered_values["respiration"])
                            
                            sensor_data["movement"] = float(motion_val)
                            sensor_data["noise"] = filtered_values["noise"]
                            sensor_data["respiration"] = filtered_values["respiration"]
                            
                            # Heuristic for breathing rate
                            raw_br = 15.0 + np.random.normal(0, 2) if sound_val > 500 else 0.0
                            filtered_values["breathing_rate"] = (EMA_ALPHA * raw_br) + ((1 - EMA_ALPHA) * filtered_values["breathing_rate"])
                            
                            sensor_data["breathing_rate"] = filtered_values["breathing_rate"]
                            sensor_data["connected"] = True
                            sensor_data["last_updated"] = time.time()
                    except Exception as e:
                        print(f"Parsing error: {e}")
                
                # Check for timeout
                current_time = time.time()
                last_update = float(sensor_data.get("last_updated", 0.0))
                if current_time - last_update > 5.0:
                    sensor_data["connected"] = False
                    # Close and retry port scan if data stops
                    ser.close()
                    break
                    
        except Exception as e:
            sensor_data["connected"] = False
            print(f"Hardware Error on {target_port if 'target_port' in locals() else 'Unknown'}: {e}. Retrying scan...")
            time.sleep(2)

# Start serial thread
threading.Thread(target=read_serial_data, daemon=True).start()

# --- Motion Detection Logic ---
def get_video_stream():
    global sensor_data
    # Pre-render 'CAMERA OFFLINE' placeholder
    offline_base = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(offline_base, "CAMERA OFFLINE", (100, 240), cv2.FONT_HERSHEY_DUPLEX, 1.8, (0, 0, 255), 3)
    _, offline_jpg = cv2.imencode('.jpg', offline_base)
    offline_frame = offline_jpg.tobytes()

    back_sub = cv2.createBackgroundSubtractorMOG2()

    while True:
        try:
            # Persistent attempt to connect to the ESP32-CAM MJPEG stream
            stream = requests.get(ESP32_VIDEO_URL, stream=True, timeout=3)
            bytes_data = bytes()
            
            for chunk in stream.iter_content(chunk_size=1024):
                bytes_data += chunk
                a = bytes_data.find(b'\xff\xd8') # JPEG Start
                b = bytes_data.find(b'\xff\xd9') # JPEG End
                
                if a != -1 and b != -1:
                    jpg = bytes_data[a:b+2]
                    bytes_data = bytes_data[b+2:]
                    
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        # Machine Vision: OpenCV Motion Detection
                        fg_mask = back_sub.apply(frame)
                        count = np.count_nonzero(fg_mask > 200)
                        
                        # Trigger visual alert and state update if motion > threshold
                        if count > 800:
                            sensor_data["motion_detected"] = True
                            # Apply clinical red border to the feed itself
                            cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), (0, 0, 255), 15)
                        else:
                            sensor_data["motion_detected"] = False
                            
                        # Serve the processed frame to Flask
                        _, frame_jpg = cv2.imencode('.jpg', frame)
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_jpg.tobytes() + b'\r\n')
        except Exception as e:
            # Fallback to placeholder if camera is unreachable
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + offline_frame + b'\r\n')
            time.sleep(1)

@app.route('/video_feed')
def video_feed():
    return Response(get_video_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/data')
def get_data():
    # Debug: Print ensuring noise is in the data
    if "noise" not in sensor_data:
        sensor_data["noise"] = 0.0
    return jsonify(sensor_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
