export type UploadResponse = {
  upload_id: string;
  filename: string;
  content_type: string;
  size: number;
  stored_filename: string;
  pdf_filename: string | null;
};

export type UploadCapabilities = {
  accept_docx: boolean;
  accept_pdf: boolean;
  convert_docx_to_pdf: boolean;
  accepted_extensions: string[];
};

export type ReconstructionAsset = {
  asset_id: string;
  filename: string;
  media_type: string;
  width: number;
  height: number;
};

export type ReconstructionResponse = {
  upload_id: string;
  html: string;
  css: string;
  warnings: string[];
  assets: ReconstructionAsset[];
  verified_link_count: number;
};
