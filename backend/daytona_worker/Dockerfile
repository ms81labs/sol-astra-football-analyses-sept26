FROM docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385
WORKDIR /workspace
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libxcb1 \
 && rm -rf /var/lib/apt/lists/*
ENV QT_QPA_PLATFORM=offscreen
ENV YOLO_AUTOINSTALL=false
ENV PYTHONPATH=/workspace
COPY backend/daytona_worker/requirements.lock /tmp/requirements.lock
RUN python -m pip uninstall --yes torchaudio \
 && python -m pip install --require-hashes --no-deps -r /tmp/requirements.lock \
 && python -m pip check
COPY lap.py /workspace/lap.py
COPY backend /workspace/backend
