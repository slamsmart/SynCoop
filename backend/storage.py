import hashlib
import os
import time

import requests

APP_NAME = "syncoop"

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")


def _cloudinary_ready() -> bool:
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)


def init_storage():
    if _cloudinary_ready():
        return {"provider": "cloudinary", "cloud_name": CLOUDINARY_CLOUD_NAME}
    raise RuntimeError("Cloudinary storage is not configured")


def _sign_cloudinary(params: dict) -> str:
    payload = "&".join(
        f"{key}={value}"
        for key, value in sorted(params.items())
        if value not in (None, "")
    )
    return hashlib.sha1(f"{payload}{CLOUDINARY_API_SECRET}".encode("utf-8")).hexdigest()


def put_object(path: str, data: bytes, content_type: str) -> dict:
    if not _cloudinary_ready():
        raise RuntimeError("Cloudinary storage is not configured")

    public_id = path.rsplit(".", 1)[0]
    timestamp = int(time.time())
    params = {
        "public_id": public_id,
        "timestamp": timestamp,
        "overwrite": "true",
    }
    signature = _sign_cloudinary(params)
    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/auto/upload"
    resp = requests.post(
        upload_url,
        data={
            **params,
            "api_key": CLOUDINARY_API_KEY,
            "signature": signature,
        },
        files={"file": (path.rsplit("/", 1)[-1], data, content_type)},
        timeout=120,
    )
    resp.raise_for_status()
    uploaded = resp.json()
    return {
        "provider": "cloudinary",
        "path": uploaded["public_id"],
        "url": uploaded["secure_url"],
        "resource_type": uploaded.get("resource_type"),
        "format": uploaded.get("format"),
        "size": uploaded.get("bytes", len(data)),
    }


def get_object(path: str):
    raise RuntimeError("Cloudinary files should be served through their secure_url")
