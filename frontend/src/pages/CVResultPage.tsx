import { useState } from "react";

import { CVPreview } from "../components/CVPreview";
import type { ReconstructionResponse } from "../types/cv";

export function CVResultPage({
  result,
  onStartOver,
}: {
  result: ReconstructionResponse;
  onStartOver: () => void;
}) {
  const [previewWarnings, setPreviewWarnings] = useState<string[]>([]);
  const warnings = [...result.warnings, ...previewWarnings];

  return (
    <main className="result-page">
      <section className="result-toolbar" aria-labelledby="result-title">
        <div>
          <p className="step-label">Reconstruction complete</p>
          <h1 id="result-title">Your editable CV</h1>
          <p className="result-intro">
            Review the reconstructed document and any details that may need your attention.
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={onStartOver}>
          Upload another CV
        </button>
      </section>

      <div className="result-layout">
        <aside className="result-sidebar" aria-label="Reconstruction details">
          <section className="result-summary">
            <span className="result-status-icon" aria-hidden="true">{"\u2713"}</span>
            <div>
              <strong>CV ready</strong>
              <span>
                {result.assets.length} extracted image{result.assets.length === 1 ? "" : "s"}
              </span>
            </div>
          </section>

          <section className="warning-panel" aria-labelledby="warnings-title">
            <div className="warning-heading">
              <span className="warning-icon" aria-hidden="true">!</span>
              <h2 id="warnings-title">Warnings</h2>
              <span className="warning-count">{warnings.length}</span>
            </div>
            {warnings.length > 0 ? (
              <ul>
                {warnings.map((warning, index) => (
                  <li key={`${index}-${warning}`}>{warning}</li>
                ))}
              </ul>
            ) : (
              <p>No reconstruction warnings were reported.</p>
            )}
          </section>

          <p className="preview-note">
            This preview is isolated from the application while you review the generated layout.
          </p>
        </aside>

        <CVPreview result={result} onValidationWarnings={setPreviewWarnings} />
      </div>
    </main>
  );
}
