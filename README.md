# CVReform

Convert uploaded PDF or DOCX CVs into structured data, editable LaTeX, and a
compiled PDF.

## Backend setup

The backend requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Start the development server:

```powershell
uvicorn app.main:app --reload
```

Alternatively, run the setup and server launcher from the project folder:

```powershell
.\run.ps1
```

To also show FastAPI request logs in the same terminal:

```powershell
.\run.ps1 -ShowBackendLogs
```

The launcher creates `.venv` if needed, installs the project dependencies, and
starts both the FastAPI and React development servers with auto-reload. Node.js
LTS is required for the frontend.

### Frontend environment

The default development configuration works without an environment file. To
override the Vite development port or FastAPI address, copy
`frontend/.env.example` to `frontend/.env` and change `VITE_DEV_PORT` or
`VITE_API_PROXY_TARGET`. The local `.env` file is ignored by Git;
`.env.example` documents the available settings.

Values prefixed with `VITE_` are included in browser-facing frontend code and
must not contain passwords, API keys, or other secrets.

The frontend is available at `http://localhost:5173`, and the API is available
at `http://127.0.0.1:8000`. Useful endpoints:

- Health check: `GET /api/v1/health`
- CV upload: `POST /api/v1/cvs/upload` (`multipart/form-data`, field name `file`)
- Interactive API documentation: `/docs`
- OpenAPI schema: `/openapi.json`

Run the test suite and linter:

```powershell
pytest
ruff check .
```
