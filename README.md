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

The launcher creates `.venv` if needed, installs the project dependencies, and
starts the development server with auto-reload.

The API is then available at `http://127.0.0.1:8000`. Useful endpoints:

- Health check: `GET /api/v1/health`
- Interactive API documentation: `/docs`
- OpenAPI schema: `/openapi.json`

Run the test suite and linter:

```powershell
pytest
ruff check .
```
