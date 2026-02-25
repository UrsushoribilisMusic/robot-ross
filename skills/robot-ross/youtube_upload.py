#!/usr/bin/env python3

import argparse
import json
import mimetypes
import os
import sys
from typing import Optional


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
YOUTUBE_UPLOAD_SCOPE = ["https://www.googleapis.com/auth/youtube.upload"]
DEFAULT_CLIENT_SECRETS = os.environ.get(
    "YOUTUBE_CLIENT_SECRETS",
    os.path.join(SCRIPT_DIR, "youtube_client_secrets.json"),
)
DEFAULT_TOKEN_FILE = os.environ.get(
    "YOUTUBE_TOKEN_FILE",
    os.path.join(SCRIPT_DIR, ".youtube_token.json"),
)
DEFAULT_CATEGORY_ID = os.environ.get("YOUTUBE_CATEGORY_ID", "22")


def _description(buyer: Optional[str], prompt: Optional[str], extra: Optional[str] = None) -> str:
    lines = ["Robot Ross drawing session."]
    if buyer:
        lines.append(f"Buyer: {buyer}")
    if prompt:
        lines.append(f"Prompt: {prompt}")
    if extra:
        lines.append(extra)
    lines.append("#Shorts")
    return "\n".join(lines)


def _build_credentials(client_secrets_file: str, token_file: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, YOUTUBE_UPLOAD_SCOPE)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not os.path.exists(client_secrets_file):
            raise FileNotFoundError(
                f"Missing OAuth client secrets file: {client_secrets_file}. "
                "Set YOUTUBE_CLIENT_SECRETS to your credentials JSON path."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file,
            YOUTUBE_UPLOAD_SCOPE,
        )
        creds = flow.run_local_server(port=0)

    with open(token_file, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())

    return creds


def youtube_upload(
    video_path: str,
    title: Optional[str] = None,
    buyer: Optional[str] = None,
    prompt: Optional[str] = None,
    description: Optional[str] = None,
    privacy_status: str = "unlisted",
    client_secrets_file: str = DEFAULT_CLIENT_SECRETS,
    token_file: str = DEFAULT_TOKEN_FILE,
) -> Optional[str]:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        print(f"[youtube_upload] Missing dependency: {exc}")
        return None

    if not os.path.exists(video_path):
        print(f"[youtube_upload] Video not found: {video_path}")
        return None

    try:
        creds = _build_credentials(client_secrets_file=client_secrets_file, token_file=token_file)
        youtube = build("youtube", "v3", credentials=creds)

        upload_title = title or f"Robot Ross drawing for {buyer or 'a customer'}"
        upload_description = _description(buyer, prompt, extra=description)
        mime, _ = mimetypes.guess_type(video_path)
        media = MediaFileUpload(video_path, mimetype=mime or "video/mp4", resumable=True)

        request = youtube.videos().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": upload_title[:100],
                    "description": upload_description[:5000],
                    "tags": ["RobotRoss", "Shorts"],
                    "categoryId": DEFAULT_CATEGORY_ID,
                },
                "status": {"privacyStatus": privacy_status},
            },
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"[youtube_upload] Upload progress: {pct}%")

        video_id = response.get("id")
        if not video_id:
            print(f"[youtube_upload] Unexpected API response: {json.dumps(response)}")
            return None
        return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as exc:
        print(f"[youtube_upload] Upload failed: {exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload a Robot Ross recording to YouTube Shorts")
    parser.add_argument("video_path", help="Path to local video file (.mov/.mp4)")
    parser.add_argument("--title", default=None, help="Video title")
    parser.add_argument("--buyer", default=None, help="Buyer name for metadata")
    parser.add_argument("--prompt", default=None, help="Prompt/content for metadata")
    parser.add_argument("--description", default=None, help="Extra description text")
    parser.add_argument(
        "--privacy-status",
        default="unlisted",
        choices=["public", "unlisted", "private"],
        help="YouTube privacy status",
    )
    args = parser.parse_args()

    url = youtube_upload(
        video_path=args.video_path,
        title=args.title,
        buyer=args.buyer,
        prompt=args.prompt,
        description=args.description,
        privacy_status=args.privacy_status,
    )
    if not url:
        return 1
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
