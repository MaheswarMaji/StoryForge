"""YouTube (Data API v3, OAuth refresh token) & Instagram (Graph API) publishing + comments."""
import os
import time
from pathlib import Path

import httpx

IG_GRAPH_HOSTS = ("https://graph.instagram.com", "https://graph.facebook.com/v21.0")

# Instagram credentials: .env fallback + runtime values persisted from the Settings page (db-backed)
IG_STATE = {
    "access_token": os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip(),
    "user_id": os.environ.get("INSTAGRAM_USER_ID", "").strip(),
    "source": "env" if os.environ.get("INSTAGRAM_ACCESS_TOKEN", "").strip() else "",
}


def set_ig_creds(token: str, user_id: str, source: str = "settings"):
    IG_STATE["access_token"] = (token or "").strip()
    IG_STATE["user_id"] = (user_id or "").strip()
    IG_STATE["source"] = source if IG_STATE["access_token"] else ""


def get_ig_creds() -> dict:
    return dict(IG_STATE)


def cred_status():
    return {
        "youtube": all(os.environ.get(k, "").strip() for k in
                       ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")),
        "youtube_oauth_setup": all(os.environ.get(k, "").strip() for k in
                                   ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET")),
        "instagram": bool(IG_STATE["access_token"] and IG_STATE["user_id"]),
    }


def ig_validate(token: str, user_id: str) -> str:
    last = None
    for base in IG_GRAPH_HOSTS:
        try:
            r = httpx.get(f"{base}/{user_id}", params={"fields": "username", "access_token": token}, timeout=30)
            if r.status_code == 200:
                return r.json().get("username", "connected")
            last = f"{base.rsplit('/', 1)[-1]}: {r.status_code} {r.text[:120]}"
        except Exception as e:
            last = str(e)[:120]
    raise RuntimeError(f"token rejected by Instagram Graph API ({last})")


def youtube_auth_url(redirect_uri: str) -> str:
    from urllib.parse import quote
    cid = os.environ["YOUTUBE_CLIENT_ID"].strip()
    return ("https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={cid}&redirect_uri={quote(redirect_uri)}&response_type=code"
            "&scope=https://www.googleapis.com/auth/youtube.force-ssl"
            "&access_type=offline&prompt=consent&include_granted_scopes=true")


def youtube_exchange_code(code: str, redirect_uri: str) -> dict:
    with httpx.Client(timeout=60) as client:
        r = client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": os.environ["YOUTUBE_CLIENT_ID"].strip(),
            "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"].strip(),
            "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
        r.raise_for_status()
        tok = r.json()
    if not tok.get("refresh_token"):
        raise RuntimeError("no refresh_token returned — revoke the app at myaccount.google.com/permissions and retry with prompt=consent")
    _save_env_key("YOUTUBE_REFRESH_TOKEN", tok["refresh_token"])
    os.environ["YOUTUBE_REFRESH_TOKEN"] = tok["refresh_token"]
    return {"ok": True}


def _save_env_key(key: str, value: str):
    path = Path(__file__).resolve().parent.parent / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [l for l in lines if not l.startswith(f"{key}=")]
    lines.append(f'{key}="{value}"')
    path.write_text("\n".join(lines) + "\n")


def _yt_client():
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"].strip(),
        client_id=os.environ["YOUTUBE_CLIENT_ID"].strip(),
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
    )
    return build("youtube", "v3", credentials=creds)


def yt_upload(video_path: Path, title: str, description: str, tags, is_kids: bool,
              thumb_path: Path = None, privacy: str = "public") -> dict:
    from googleapiclient.http import MediaFileUpload

    yt = _yt_client()
    body = {
        "snippet": {"title": title[:100], "description": description[:4900],
                    "tags": [t for t in tags if t][:25], "categoryId": "24"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(is_kids)},
    }
    media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
    video_id = resp["id"]
    if thumb_path and Path(thumb_path).exists():
        try:
            yt.thumbnails().set(videoId=video_id,
                                media_body=MediaFileUpload(str(thumb_path))).execute()
        except Exception as e:
            print(f"[social] thumbnail set failed: {str(e)[:120]}")
    return {"video_id": video_id, "url": f"https://www.youtube.com/shorts/{video_id}"}


def yt_list_comments(video_id: str, max_results: int = 50):
    yt = _yt_client()
    resp = yt.commentThreads().list(
        part="snippet", videoId=video_id, maxResults=max_results, order="time").execute()
    out = []
    for item in resp.get("items", []):
        c = item["snippet"]["topLevelComment"]["snippet"]
        out.append({
            "comment_id": item["snippet"]["topLevelComment"]["id"],
            "author": c.get("authorDisplayName", ""),
            "text": c.get("textOriginal", "")[:600],
            "likes": c.get("likeCount", 0),
            "ts": c.get("publishedAt", ""),
        })
    return out


def yt_channel_info() -> dict:
    yt = _yt_client()
    r = yt.channels().list(part="snippet,statistics", mine=True).execute()
    items = r.get("items", [])
    if not items:
        return {}
    st = items[0].get("statistics", {})
    return {"channel_id": items[0]["id"], "title": items[0]["snippet"].get("title", ""),
            "subscribers": int(st.get("subscriberCount", 0) or 0),
            "total_views": int(st.get("viewCount", 0) or 0),
            "videos": int(st.get("videoCount", 0) or 0)}


def yt_video_stats(video_ids) -> dict:
    if not video_ids:
        return {}
    yt = _yt_client()
    out = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        r = yt.videos().list(part="statistics", ids=",".join(chunk)).execute()
        for it in r.get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = {"views": int(s.get("viewCount", 0) or 0),
                             "likes": int(s.get("likeCount", 0) or 0),
                             "comments": int(s.get("commentCount", 0) or 0)}
    return out


def yt_reply(comment_id: str, text: str) -> str:
    yt = _yt_client()
    r = yt.comments().insert(part="snippet", body={
        "snippet": {"parentId": comment_id, "textOriginal": text[:900]}}).execute()
    return r["id"]


# ---------- Instagram ----------
def ig_publish(video_url: str, caption: str, thumb_url: str = None) -> dict:
    tok, uid = IG_STATE["access_token"], IG_STATE["user_id"]
    if not tok or not uid:
        raise RuntimeError("Instagram not connected — add credentials in Settings → Integrations")
    graph = IG_GRAPH_HOSTS[1]
    with httpx.Client(timeout=60) as client:
        data = {"media_type": "REELS", "video_url": video_url, "caption": caption[:2200],
                "access_token": tok}
        if thumb_url:
            data["thumb_url"] = thumb_url
        r = client.post(f"{graph}/{uid}/media", data=data)
        r.raise_for_status()
        creation_id = r.json()["id"]
        for _ in range(60):
            s = client.get(f"{graph}/{creation_id}?fields=status_code&access_token={tok}").json()
            if s.get("status_code") == "FINISHED":
                break
            if s.get("status_code") == "ERROR":
                raise RuntimeError(f"IG processing failed: {s}")
            time.sleep(4)
        pub = client.post(f"{graph}/{uid}/media_publish",
                          data={"creation_id": creation_id, "access_token": tok})
        pub.raise_for_status()
        post_id = pub.json()["id"]
    return {"post_id": post_id, "url": f"https://www.instagram.com/reel/{post_id}/"}


def ig_list_comments(max_media: int = 5):
    tok, uid = IG_STATE["access_token"], IG_STATE["user_id"]
    if not tok or not uid:
        raise RuntimeError("Instagram not connected")
    graph = IG_GRAPH_HOSTS[1]
    out = []
    with httpx.Client(timeout=60) as client:
        medias = client.get(f"{graph}/{uid}/media?fields=id&limit={max_media}&access_token={tok}").json()
        for m in medias.get("data", []):
            cs = client.get(f"{graph}/{m['id']}/comments?fields=id,text,timestamp,username&access_token={tok}").json()
            for c in cs.get("data", []):
                out.append({"comment_id": c["id"], "author": c.get("username", ""),
                            "text": c.get("text", "")[:600], "likes": 0,
                            "ts": c.get("timestamp", ""), "video_id": m["id"]})
    return out


def ig_reply(comment_id: str, text: str) -> str:
    tok = IG_STATE["access_token"]
    if not tok:
        raise RuntimeError("Instagram not connected")
    graph = IG_GRAPH_HOSTS[1]
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{graph}/{comment_id}/replies",
                        data={"message": text[:900], "access_token": tok})
        r.raise_for_status()
        return r.json().get("id", "")
