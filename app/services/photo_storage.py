"""
Storage for diagnostic photos.

Photos back warranty disputes, so they must never be deleted or
overwritten by the application - only added. The local backend is fine for
a single-shop deployment; for anything with multiple bays writing
concurrently, or for real disaster-recovery guarantees, switch
PHOTO_STORAGE_BACKEND to "s3" (see docs/DEPLOYMENT.md for the setup).
"""
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


class UnsupportedFileType(Exception):
    pass


def _extension(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def save_diagnostic_photo(file_storage, job_number):
    """Persist an uploaded photo and return storage metadata.

    ``file_storage`` is a werkzeug FileStorage (from request.files). Returns
    a dict with storage_backend, storage_path, original_filename,
    content_type, file_size_bytes - ready to build a DiagnosticPhoto row.
    """
    original_filename = secure_filename(file_storage.filename or "photo")
    ext = _extension(original_filename)
    allowed = current_app.config["ALLOWED_PHOTO_EXTENSIONS"]
    if ext not in allowed:
        raise UnsupportedFileType(
            f"'.{ext}' is not an accepted photo type. Allowed: {sorted(allowed)}"
        )

    backend = current_app.config["PHOTO_STORAGE_BACKEND"]
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    if backend == "local":
        job_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], job_number)
        os.makedirs(job_dir, exist_ok=True)
        dest_path = os.path.join(job_dir, unique_name)
        file_storage.save(dest_path)
        size = os.path.getsize(dest_path)
        return {
            "storage_backend": "local",
            "storage_path": os.path.relpath(
                dest_path, current_app.config["UPLOAD_FOLDER"]
            ),
            "original_filename": original_filename,
            "content_type": file_storage.mimetype,
            "file_size_bytes": size,
        }

    if backend == "s3":  # pragma: no cover - requires real AWS credentials
        import boto3

        bucket = current_app.config["S3_BUCKET_NAME"]
        key = f"{job_number}/{unique_name}"
        client = boto3.client("s3", region_name=current_app.config["AWS_REGION"])
        client.upload_fileobj(file_storage, bucket, key)
        return {
            "storage_backend": "s3",
            "storage_path": key,
            "original_filename": original_filename,
            "content_type": file_storage.mimetype,
            "file_size_bytes": None,
        }

    raise ValueError(f"Unknown PHOTO_STORAGE_BACKEND: {backend!r}")


def photo_url(photo):
    """Build a URL the staff UI can use to display a stored photo."""
    if photo.storage_backend == "local":
        from flask import url_for

        return url_for(
            "staff.diagnostic_photo", path=photo.storage_path.replace(os.sep, "/")
        )
    if photo.storage_backend == "s3":  # pragma: no cover
        bucket = current_app.config["S3_BUCKET_NAME"]
        region = current_app.config["AWS_REGION"]
        return f"https://{bucket}.s3.{region}.amazonaws.com/{photo.storage_path}"
    raise ValueError(f"Unknown storage backend: {photo.storage_backend!r}")
