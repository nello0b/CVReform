import { type ChangeEvent, type FormEvent, useRef, useState } from "react";

const acceptedExtensions = [".pdf", ".docx"];

function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function selectFile(file?: File) {
    setMessage("");

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!acceptedExtensions.includes(extension)) {
      setSelectedFile(null);
      setError("Please choose a PDF or DOCX file.");
      return;
    }

    setError("");
    setSelectedFile(file);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0]);
  }

  function clearFile() {
    setSelectedFile(null);
    setError("");
    setMessage("");
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setError("Choose a CV before continuing.");
      return;
    }

    setMessage("Your CV is ready. The upload endpoint will be connected in the next task.");
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="CVReform home">
          <img src="/favicon.svg" alt="" />
          <span>CVReform</span>
        </a>
        <span className="header-note">Editable CVs, without starting over</span>
      </header>

      <main className="page">
        <section className="hero" aria-labelledby="page-title">
          <p className="eyebrow">PDF or DOCX to LaTeX</p>
          <h1 id="page-title">Turn your current CV into an editable document.</h1>
          <p className="intro">
            Upload your CV and CVReform will preserve its information while preparing a clean,
            editable LaTeX version and a new PDF.
          </p>
        </section>

        <section className="upload-card" aria-labelledby="upload-title">
          <div className="card-heading">
            <div>
              <p className="step-label">Step 1</p>
              <h2 id="upload-title">Upload your CV</h2>
            </div>
            <span className="format-pill">PDF or DOCX</span>
          </div>

          <form onSubmit={handleSubmit}>
            <label className="file-picker" htmlFor="cv-file">
              <span className="upload-icon" aria-hidden="true">↑</span>
              <span className="picker-title">
                {selectedFile ? "Choose a different file" : "Choose your CV"}
              </span>
              <span className="picker-help">Select one PDF or DOCX document from your computer</span>
            </label>
            <input
              ref={inputRef}
              className="sr-only"
              id="cv-file"
              name="cv-file"
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleFileChange}
            />

            {selectedFile && (
              <div className="selected-file">
                <div className="file-type" aria-hidden="true">
                  {selectedFile.name.split(".").pop()?.toUpperCase()}
                </div>
                <div className="file-details">
                  <strong>{selectedFile.name}</strong>
                  <span>{formatFileSize(selectedFile.size)}</span>
                </div>
                <button className="remove-button" type="button" onClick={clearFile}>
                  Remove
                </button>
              </div>
            )}

            <p className="form-message form-message--error" role="alert">
              {error}
            </p>

            <button className="primary-button" type="submit" disabled={!selectedFile}>
              Continue with this CV
            </button>

            <p className="form-message form-message--success" role="status" aria-live="polite">
              {message}
            </p>
          </form>

          <p className="privacy-note">Your document is only used to prepare your converted CV.</p>
        </section>
      </main>
    </div>
  );
}

export default App;
