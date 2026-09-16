# Tech Context

## Languages And Frameworks

- Python backend
- FastAPI for the HTTP API
- React 19 + TypeScript + Vite frontend
- SQLite plus JSON/CSV artifact files for persistence

## Key Backend Dependencies

From `backend/requirements.txt`, the important stack pieces are:

- `fastapi`, `starlette`, `uvicorn`
- `pydantic`
- `pytest`
- `opencv-python`
- `torch`, `torchvision`
- `ultralytics`
- `numpy`, `scipy`, `pandas`, `polars`
- `boto3`, `httpx`, `requests`

## Key Frontend Dependencies

From `frontend/package.json`, the important stack pieces are:

- `react`, `react-dom`
- `vite`
- `typescript`
- `vitest`
- `eslint`
- `@google/genai`
- `apache-arrow`, `parquet-wasm`

## Runtime Modes

The project supports:

- local processing on the current machine
- RunPod-backed remote processing through SSH-connected pods

Remote work is pod-oriented rather than serverless-oriented.

## Important Paths

- backend API/application code: `backend/app/`
- proof and batch scripts: `backend/scripts/`
- core pipeline entrypoint: `backend/run_guerilla.py`
- frontend app: `frontend/src/`
- manifests: `backend/benchmark_suites/`
- generated truth artifacts: `backend/storage/`

## Development Commands

Backend:

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Common verification:

```bash
python3 -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend build
```

## Technical Constraints

- local hardware is often not enough for heavy multi-model inference screens
- that is why detector breadth screening was moved to RunPod
- current saved truth is heavily shaped by one failing source clip, `trimed-5min.mp4`
- generated artifacts under `backend/storage/` are operationally critical, even though they are not normal source files
- local-only runtime state such as `backend/storage/`, `videos/`, virtualenvs, and model weights should stay out of source control unless intentionally preserved

## Tooling Preferences

- prefer `pytest` for backend verification
- prefer pod-based RunPod workflows with explicit cleanup
- prefer reading generated JSON truth surfaces over guessing from historical notes
- prefer focused scripts under `backend/scripts/` for repeatable operations
