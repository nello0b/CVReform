# CVReform

Convert uploaded DOCX or PDF CVs into editable web documents while preserving their visual style.

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

For the first setup after cloning the project:

```powershell
.\setup.ps1
```

This installs the backend and frontend project dependencies. When optional PDF
support is enabled, setup also checks for LibreOffice and installs it when
necessary. After setup, start the development servers with:

```powershell
.\run.ps1
```

To also show FastAPI request logs in the same terminal:

```powershell
.\run.ps1 -ShowBackendLogs
```

To enable verbose backend logs and print safe metadata for each uploaded CV:

```powershell
.\run.ps1 -Debug
```

Debug mode prints the filename, extension, reported content type, byte size,
saved upload path, and any generated PDF path. It never prints the CV contents.

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

### Backend environment

Backend feature flags live in the root `.env` file. `setup.ps1` creates it from
`.env.example` without replacing existing local choices.

```dotenv
CVREFORM_ACCEPT_DOCX=true
CVREFORM_ACCEPT_PDF=true
CVREFORM_CONVERT_DOCX_TO_PDF=true
SOFFICE_PATH=
```

Each behavior can be controlled independently:

- `CVREFORM_ACCEPT_DOCX` controls DOCX uploads.
- `CVREFORM_ACCEPT_PDF` controls PDF uploads.
- `CVREFORM_CONVERT_DOCX_TO_PDF` creates a PDF visual reference after a DOCX upload.

The frontend automatically shows whichever input formats the API reports. LibreOffice
is only required when DOCX input and DOCX-to-PDF conversion are both enabled.
`SOFFICE_PATH` is only needed when LibreOffice is installed outside its standard
Windows location.

The frontend is available at `http://localhost:5173`, and the API is available
at `http://127.0.0.1:8000`. Useful endpoints:

- Health check: `GET /api/v1/health`
- Upload capabilities: `GET /api/v1/cvs/capabilities`
- CV upload: `POST /api/v1/cvs/upload` (`multipart/form-data`, field name `file`)
- Interactive API documentation: `/docs`
- OpenAPI schema: `/openapi.json`

Run the test suite and linter:

```powershell
pytest
ruff check .
```

### Planned HTML generation

The upload endpoint validates and stores each enabled input format. DOCX files
can also receive a PDF visual reference through LibreOffice. The next processing
stage will use the document's extracted content and rendered appearance to
generate editable HTML and CSS.
