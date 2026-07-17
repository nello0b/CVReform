import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";

import { getUploadCapabilities, reconstructCV, uploadCV } from "../api/cvApi";
import {
  acceptedMimeTypes,
  formatAcceptedFormats,
  formatFileSize,
} from "../lib/formatters";
import type {
  ReconstructionResponse,
  UploadCapabilities,
  UploadResponse,
} from "../types/cv";

const maxUploadSize = 10 * 1024 * 1024;
const defaultCapabilities: UploadCapabilities = {
  accept_docx: true,
  accept_pdf: false,
  convert_docx_to_pdf: false,
  accepted_extensions: [".docx"],
};

export function CVUploadPage({
  onReconstructed,
}: {
  onReconstructed: (result: ReconstructionResponse) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isReconstructing, setIsReconstructing] = useState(false);
  const [capabilities, setCapabilities] =
    useState<UploadCapabilities>(defaultCapabilities);

  useEffect(() => {
    const controller = new AbortController();

    async function loadCapabilities() {
      try {
        setCapabilities(await getUploadCapabilities(controller.signal));
      } catch (capabilitiesError) {
        const requestWasAborted =
          capabilitiesError instanceof DOMException && capabilitiesError.name === "AbortError";
        if (!requestWasAborted) {
          console.warn("Could not load upload capabilities.", capabilitiesError);
        }
      }
    }

    void loadCapabilities();
    return () => controller.abort();
  }, []);

  const acceptedFormatLabel = formatAcceptedFormats(capabilities.accepted_extensions);
  const uploadsEnabled = capabilities.accept_docx || capabilities.accept_pdf;

  function selectFile(file?: File) {
    setMessage("");
    setUploadResult(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    const extensionStart = file.name.lastIndexOf(".");
    const extension = extensionStart >= 0 ? file.name.slice(extensionStart).toLowerCase() : "";
    if (!capabilities.accepted_extensions.includes(extension)) {
      setSelectedFile(null);
      setError(`Please choose a ${acceptedFormatLabel} file.`);
      return;
    }

    if (file.size > maxUploadSize) {
      setSelectedFile(null);
      setError("Please choose a file smaller than 10 MB.");
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
    setUploadResult(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setError("Choose a CV before continuing.");
      return;
    }

    setError("");
    setMessage("");
    setUploadResult(null);
    setIsUploading(true);

    try {
      const result = await uploadCV(selectedFile);
      setUploadResult(result);
      setMessage("Your CV was uploaded successfully and is ready for processing.");
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "The CV could not be uploaded. Please try again.",
      );
    } finally {
      setIsUploading(false);
    }
  }

  async function handleReconstruct() {
    if (!uploadResult) {
      return;
    }
    if (!uploadResult.pdf_filename) {
      setError("This CV must be converted to PDF before it can be reconstructed.");
      return;
    }

    setError("");
    setMessage("");
    setIsReconstructing(true);

    try {
      onReconstructed(await reconstructCV(uploadResult.upload_id));
    } catch (reconstructionError) {
      setError(
        reconstructionError instanceof Error
          ? reconstructionError.message
          : "The CV could not be reconstructed. Please try again.",
      );
    } finally {
      setIsReconstructing(false);
    }
  }

  return (
    <main className="page">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">CV to editable web document</p>
        <h1 id="page-title">Turn your current CV into an editable document.</h1>
        <p className="intro">
          Upload your CV and CVReform will preserve its information while preparing a clean,
          editable web version that preserves its visual style.
        </p>
      </section>

      <section className="upload-card" aria-labelledby="upload-title">
        <div className="card-heading">
          <div>
            <p className="step-label">Step 1</p>
            <h2 id="upload-title">Upload your CV</h2>
          </div>
          <span className="format-pill">{acceptedFormatLabel}</span>
        </div>

        <form onSubmit={handleSubmit}>
          <label
            className={`file-picker${isUploading || !uploadsEnabled ? " file-picker--disabled" : ""}`}
            htmlFor="cv-file"
          >
            <span className="upload-icon" aria-hidden="true">{"\u2191"}</span>
            <span className="picker-title">
              {selectedFile ? "Choose a different file" : "Choose your CV"}
            </span>
            <span className="picker-help">
              {uploadsEnabled
                ? `Select one ${acceptedFormatLabel} document from your computer`
                : "Uploads are disabled by configuration"}
            </span>
          </label>
          <input
            ref={inputRef}
            className="sr-only"
            id="cv-file"
            name="cv-file"
            type="file"
            accept={acceptedMimeTypes(capabilities)}
            onChange={handleFileChange}
            disabled={isUploading || !uploadsEnabled}
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
              <button
                className="remove-button"
                type="button"
                onClick={clearFile}
                disabled={isUploading}
              >
                Remove
              </button>
            </div>
          )}

          <p className="form-message form-message--error" role="alert">
            {error}
          </p>

          <button
            className="primary-button"
            type="submit"
            disabled={!selectedFile || isUploading || !uploadsEnabled}
          >
            {isUploading ? "Uploading CV..." : "Upload CV"}
          </button>

          {uploadResult && (
            <button
              className="primary-button reconstruct-button"
              type="button"
              onClick={() => void handleReconstruct()}
              disabled={isReconstructing || !uploadResult.pdf_filename}
            >
              {isReconstructing ? "Reconstructing your CV..." : "Create editable CV"}
            </button>
          )}

          <p className="form-message form-message--success" role="status" aria-live="polite">
            {message}
          </p>
          {uploadResult && (
            <p className="upload-reference">
              Upload reference: <code>{uploadResult.upload_id}</code>
            </p>
          )}
        </form>

        <p className="privacy-note">Your document is only used to prepare your converted CV.</p>
      </section>
    </main>
  );
}
