/** Photo gallery for one activity: thumbnails, add (drop or browse), enlarge, delete.

 * Image bytes are fetched by <img> tags from the serve endpoint; they
 * authenticate with the session cookie (M22a), so no token appears in URLs.
 */

import { useCallback, useEffect, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";

import {
  imageServeUrl,
  useActivityImages,
  useDeleteImage,
  useUploadImage,
} from "../api/hooks";

type ActivityImagesProps = {
  activityId: string;
};

export default function ActivityImages({ activityId }: ActivityImagesProps) {
  const { data, isPending, isError } = useActivityImages(activityId);
  const uploadMutation = useUploadImage(activityId);
  const deleteMutation = useDeleteImage(activityId);

  const [enlarged, setEnlarged] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Close the lightbox with Escape.
  useEffect(() => {
    if (enlarged === null) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setEnlarged(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [enlarged]);

  const images = data?.items ?? [];

  const onDrop = useCallback(
    (accepted: File[], rejections: FileRejection[]) => {
      setUploadError(null);
      if (rejections.length > 0) {
        const rejected = rejections[0].file;
        setUploadError(
          `${rejected.name} was not accepted. Photos must be JPEG, PNG or WebP.`,
        );
        return;
      }
      // One upload per file, in order.
      accepted.forEach((file) => {
        setUploadError(null);
        uploadMutation.mutate(file, {
          onError: (error) => setUploadError(error instanceof Error ? error.message : "Upload failed."),
        });
      });
    },
    [uploadMutation],
  );

  const { getRootProps, getInputProps } = useDropzone({
    onDrop,
    accept: {
      "image/jpeg": [".jpg", ".jpeg"],
      "image/png": [".png"],
      "image/webp": [".webp"],
    },
    multiple: true,
    noKeyboard: false,
  });

  function handleDelete(imageId: string) {
    if (window.confirm("Remove this photo? This cannot be undone.")) {
      deleteMutation.mutate(imageId);
    }
  }

  if (isPending) {
    return <p className="py-4 text-sm text-ink-muted">Loading photos…</p>;
  }

  if (isError) {
    return <p className="py-4 text-sm text-danger">Photos could not be loaded.</p>;
  }

  return (
    <div>
      {images.length === 0 ? (
        <p className="mb-3 text-sm text-ink-muted">No photos yet.</p>
      ) : null}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-3">
        {images.map((image) => (
          <div key={image.id} className="group relative">
            <button
              type="button"
              onClick={() => setEnlarged(image.id)}
              title={image.original_filename ?? "View photo"}
              className="block w-full cursor-zoom-in overflow-hidden rounded-md border border-line"
            >
              <img
                src={imageServeUrl(activityId, image.id)}
                alt={image.original_filename ?? "Activity photo"}
                loading="lazy"
                className="aspect-square w-full object-cover"
              />
            </button>
            <button
              type="button"
              onClick={() => handleDelete(image.id)}
              disabled={deleteMutation.isPending}
              aria-label="Remove photo"
              title="Remove photo"
              className="absolute right-1.5 top-1.5 hidden h-6 w-6 items-center justify-center rounded-full bg-black/60 text-xs leading-none text-white hover:bg-danger group-hover:flex focus-visible:flex"
            >
              ×
            </button>
          </div>
        ))}

        <div
          {...getRootProps()}
          className={`flex aspect-square cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed text-xs transition-colors ${
            uploadMutation.isPending
              ? "border-line opacity-60"
              : "border-line bg-surface text-ink-muted hover:border-accent"
          }`}
        >
          <input {...getInputProps()} />
          <span className="text-2xl leading-none">+</span>
          <span>{uploadMutation.isPending ? "Adding…" : "Add photos"}</span>
        </div>
      </div>

      {uploadError !== null && (
        <p role="alert" className="mt-3 text-xs text-danger">
          {uploadError}
        </p>
      )}

      {enlarged !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6"
          onClick={() => setEnlarged(null)}
        >
          <img
            src={imageServeUrl(activityId, enlarged)}
            alt="Photo (enlarged)"
            className="max-h-full max-w-full rounded-md"
          />
          <button
            type="button"
            onClick={() => setEnlarged(null)}
            aria-label="Close enlarged photo"
            className="absolute right-5 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-black/60 text-lg leading-none text-white hover:bg-danger"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
