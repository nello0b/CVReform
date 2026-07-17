import { useMemo, useRef, useState } from "react";

import { createPreviewDocument } from "../lib/previewDocument";
import type { ReconstructionResponse } from "../types/cv";

const minimumPreviewZoom = 50;
const maximumPreviewZoom = 150;
const previewZoomStep = 10;
const safeLinkProtocols = ["http:", "https:", "mailto:", "tel:"];

type CVPreviewProps = {
  result: ReconstructionResponse;
  onValidationWarnings: (warnings: string[]) => void;
};

function findPageOverflowWarnings(document: Document) {
  const pages = Array.from(
    document.querySelectorAll<HTMLElement>(".cv-document > .cv-page"),
  );
  const fallbackDocument = document.querySelector<HTMLElement>(".cv-document");
  const measuredPages = pages.length > 0 ? pages : fallbackDocument ? [fallbackDocument] : [];

  return measuredPages.flatMap((page, index) => {
    const verticalOverflow = page.scrollHeight > page.clientHeight + 1;
    const horizontalOverflow = page.scrollWidth > page.clientWidth + 1;
    if (!verticalOverflow && !horizontalOverflow) {
      return [];
    }

    const pageNumber = page.dataset.page || String(index + 1);
    const direction = verticalOverflow && horizontalOverflow
      ? "vertically and horizontally"
      : verticalOverflow
        ? "vertically"
        : "horizontally";
    return [`Page ${pageNumber} content overflows ${direction} and is being clipped.`];
  });
}

export function CVPreview({ result, onValidationWarnings }: CVPreviewProps) {
  const previewRef = useRef<HTMLIFrameElement>(null);
  const [previewZoom, setPreviewZoom] = useState(100);
  const [selectedLink, setSelectedLink] = useState("");
  const [linkWasCopied, setLinkWasCopied] = useState(false);
  const previewDocument = useMemo(
    () => createPreviewDocument(result, previewZoom),
    [result, previewZoom],
  );

  function changePreviewZoom(change: number) {
    setPreviewZoom((currentZoom) =>
      Math.min(maximumPreviewZoom, Math.max(minimumPreviewZoom, currentZoom + change)),
    );
  }

  function handlePreviewLoad() {
    const iframeDocument = previewRef.current?.contentDocument;
    if (!iframeDocument) {
      return;
    }

    iframeDocument.addEventListener("click", (event) => {
      const target = event.target as Element | null;
      if (!target || typeof target.closest !== "function") {
        return;
      }

      const link = target.closest("a[href]") as HTMLAnchorElement | null;
      const rawDestination = link?.getAttribute("href")?.trim();
      if (!rawDestination || rawDestination === "#") {
        return;
      }

      event.preventDefault();
      const destination = new URL(rawDestination, window.location.origin);
      if (!safeLinkProtocols.includes(destination.protocol)) {
        return;
      }

      setSelectedLink(destination.href);
      setLinkWasCopied(false);
    });

    // Measure the browser's real layout after it has painted. This catches generated
    // typography or spacing that cannot fit inside the fixed physical page boundary.
    const iframeWindow = iframeDocument.defaultView;
    if (iframeWindow) {
      iframeWindow.requestAnimationFrame(() => {
        onValidationWarnings(findPageOverflowWarnings(iframeDocument));
      });
    } else {
      onValidationWarnings(findPageOverflowWarnings(iframeDocument));
    }
  }

  async function copySelectedLink() {
    await navigator.clipboard.writeText(selectedLink);
    setLinkWasCopied(true);
  }

  return (
    <section className="preview-panel" aria-labelledby="preview-title">
      <div className="preview-heading">
        <div>
          <p className="step-label">Document preview</p>
          <h2 id="preview-title">Generated HTML and CSS</h2>
        </div>
        <div className="preview-actions">
          <div className="zoom-controls" aria-label="CV preview zoom">
            <button
              type="button"
              aria-label="Zoom out"
              title="Zoom out"
              onClick={() => changePreviewZoom(-previewZoomStep)}
              disabled={previewZoom === minimumPreviewZoom}
            >
              {"\u2212"}
            </button>
            <button
              className="zoom-value"
              type="button"
              aria-label={`Reset zoom. Current zoom ${previewZoom}%`}
              title="Reset zoom"
              onClick={() => setPreviewZoom(100)}
            >
              {previewZoom}%
            </button>
            <button
              type="button"
              aria-label="Zoom in"
              title="Zoom in"
              onClick={() => changePreviewZoom(previewZoomStep)}
              disabled={previewZoom === maximumPreviewZoom}
            >
              +
            </button>
          </div>
          <span className="preview-badge">A4 preview</span>
        </div>
      </div>
      <iframe
        ref={previewRef}
        className="cv-preview"
        title="Reconstructed CV preview"
        sandbox="allow-same-origin"
        srcDoc={previewDocument}
        onLoad={handlePreviewLoad}
      />
      {selectedLink && (
        <div className="link-inspector" role="status" aria-live="polite">
          <div className="link-inspector-copy">
            <span>CV link selected</span>
            <strong title={selectedLink}>{selectedLink}</strong>
          </div>
          <div className="link-inspector-actions">
            <button type="button" onClick={() => void copySelectedLink()}>
              {linkWasCopied ? "Copied" : "Copy link"}
            </button>
            <a href={selectedLink} target="_blank" rel="noreferrer">
              Open in new tab
            </a>
            <button
              className="link-inspector-close"
              type="button"
              aria-label="Close link details"
              title="Close"
              onClick={() => setSelectedLink("")}
            >
              {"\u00d7"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
