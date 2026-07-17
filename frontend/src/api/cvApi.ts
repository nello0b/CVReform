import type {
  ReconstructionResponse,
  UploadCapabilities,
  UploadResponse,
} from "../types/cv";

type ErrorResponse = {
  detail?: string;
};

async function readResponse<T>(response: Response, fallbackMessage: string): Promise<T> {
  let body: (T & ErrorResponse) | null = null;
  try {
    body = (await response.json()) as T & ErrorResponse;
  } catch {
    // A malformed or empty API response should still become a useful user-facing error.
  }

  if (!response.ok || body === null) {
    throw new Error(body?.detail || fallbackMessage);
  }

  return body;
}

export async function getUploadCapabilities(signal: AbortSignal) {
  const response = await fetch("/api/v1/cvs/capabilities", { signal });
  return readResponse<UploadCapabilities>(response, "Upload capabilities could not be loaded.");
}

export async function uploadCV(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/v1/cvs/upload", {
    method: "POST",
    body: formData,
  });
  return readResponse<UploadResponse>(response, "The CV could not be uploaded.");
}

export async function reconstructCV(uploadId: string) {
  const response = await fetch(`/api/v1/cvs/${uploadId}/reconstruct`, {
    method: "POST",
  });
  return readResponse<ReconstructionResponse>(
    response,
    "The CV could not be reconstructed.",
  );
}
