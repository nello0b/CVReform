import { useState } from "react";

import { SiteHeader } from "./components/SiteHeader";
import { CVResultPage } from "./pages/CVResultPage";
import { CVUploadPage } from "./pages/CVUploadPage";
import type { ReconstructionResponse } from "./types/cv";

function App() {
  const [reconstructionResult, setReconstructionResult] =
    useState<ReconstructionResponse | null>(null);

  const showingResult = reconstructionResult !== null;

  return (
    <div className={`app-shell${showingResult ? " app-shell--result" : ""}`}>
      <SiteHeader expanded={showingResult} />
      {reconstructionResult ? (
        <CVResultPage
          result={reconstructionResult}
          onStartOver={() => setReconstructionResult(null)}
        />
      ) : (
        <CVUploadPage onReconstructed={setReconstructionResult} />
      )}
    </div>
  );
}

export default App;
