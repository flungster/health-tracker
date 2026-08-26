/** Drag-and-drop upload zone built on react-dropzone. */

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";

const ACCEPTED_EXTENSIONS = [".gpx", ".tcx", ".fit"];

type UploadZoneProps = {
  onFileSelected: (file: File | null) => void;
};

export default function UploadZone({ onFileSelected }: UploadZoneProps) {
  const [rejectedName, setRejectedName] = useState<string | null>(null);

  const onDrop = useCallback(
    (accepted: File[], rejections: Array<{ file: File }>) => {
      setRejectedName(null);
      if (rejections.length > 0) {
        setRejectedName(rejections[0].file.name);
        return;
      }
      if (accepted.length === 0) {
        return;
      }
      onFileSelected(accepted[0]);
    },
    [onFileSelected],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/octet-stream": ACCEPTED_EXTENSIONS,
    },
    noKeyboard: true,
    maxFiles: 1,
  });

  return (
    <div
      {...getRootProps()}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-14 text-center transition-colors ${
        isDragActive ? "border-accent bg-accent-soft" : "border-line bg-surface hover:border-ink-faint"
      }`}
    >
      <input {...getInputProps()} />
      <svg
        className="mb-3 h-10 w-10 text-ink-faint"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"
        />
      </svg>
      <p className="text-sm font-medium text-ink">
        {isDragActive ? "Drop the file here" : "Drag & drop an activity file"}
      </p>
      <p className="mt-1 text-xs text-ink-muted">
        or click to browse — .gpx, .tcx, .fit
      </p>
      {rejectedName !== null && (
        <p className="mt-3 text-xs text-danger">
          {rejectedName} is not a supported activity file.
        </p>
      )}
    </div>
  );
}
