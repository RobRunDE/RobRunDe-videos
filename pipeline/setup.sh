#!/usr/bin/env bash
# One-time setup per session: python packages + the Piper voice from config.json.
set -e
cd "$(dirname "$0")"
pip install --break-system-packages -q piper-tts pillow numpy 2>&1 | grep -v -i warning || true
# FSRCNN (.pb) upscaler needs an OpenCV with dnn_superres that still reads TensorFlow graphs
if ! python3 -c "import cv2;s=cv2.dnn_superres.DnnSuperResImpl_create();s.readModel('models/FSRCNN_x2.pb')" 2>/dev/null; then
  pip install --break-system-packages -q "opencv-contrib-python-headless==4.10.0.84" 2>&1 | grep -v -i warning || true
fi
V=$(python3 -c "import json;print(json.load(open('config.json'))['voice'])")
P=$(python3 -c "import json;c=json.load(open('config.json'));print(c['voice_paths'][c['voice']])")
B=$(python3 -c "import json;print(json.load(open('config.json'))['voice_url_base'])")
mkdir -p voices
if [ ! -s "voices/$V.onnx" ]; then
  curl -sSL -o "voices/$V.onnx" "$B/$P.onnx"
  curl -sSL -o "voices/$V.onnx.json" "$B/$P.onnx.json"
fi
python3 -c "import cv2;s=cv2.dnn_superres.DnnSuperResImpl_create();s.readModel('models/FSRCNN_x2.pb')"
which ffmpeg >/dev/null
echo "setup ok: voice=$V"
