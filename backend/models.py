import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _oid(v):
    return str(v) if isinstance(v, ObjectId) else v


PyObjectId = Annotated[str, BeforeValidator(_oid)]


def utcnow():
    return datetime.now(timezone.utc)


class BaseDocument(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")

    @classmethod
    def from_mongo(cls, doc):
        return cls(**doc) if doc else None

    def to_mongo(self):
        return self.model_dump(by_alias=True, exclude_none=True)


class Channel(BaseDocument):
    key: str = ""
    name: str = ""
    description: str = ""
    language: str = "hi"
    tone: str = ""
    voice: str = "onyx"
    voice_speed: float = 1.0
    music_mood: str = "devotional"
    music_volume: float = 0.16
    safety_level: str = "general"
    style_prefix: str = ""
    cta_text: str = ""
    is_kids: bool = False
    expressive_voice: bool = True
    mode: str = "slide"
    video_type: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Book(BaseDocument):
    filename: str = ""
    channel_id: str = ""
    owner_id: str = ""
    path: str = ""
    storage_path: str = ""
    size_bytes: int = 0
    status: str = "uploaded"
    progress: int = 0
    languages: List[str] = []
    pages: List[Dict[str, Any]] = []
    total_pages: int = 0
    structured: Dict[str, Any] = {}
    error: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Story(BaseDocument):
    book_id: str = ""
    channel_id: str = ""
    owner_id: str = ""
    title_hindi: str = ""
    title_english: str = ""
    source: str = ""
    page_start: int = 0
    page_end: int = 0
    category: str = ""
    characters: List[Dict[str, str]] = []
    setting: str = ""
    conflict: str = ""
    twist: str = ""
    climax: str = ""
    resolution: str = ""
    moral: str = ""
    emotional_tone: str = ""
    target_audience: str = ""
    visual_style: str = ""
    estimated_length: str = "90s"
    status: str = "draft"
    stage: str = ""
    mode: str = "slide"
    target_seconds: int = 90
    source_text: str = ""
    script: Dict[str, Any] = {}
    character_sheet: Dict[str, Any] = {}
    qa: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    media: Dict[str, Any] = {}
    review_notes: str = ""
    publish: Dict[str, Any] = {}
    improvements: List[Dict[str, Any]] = []
    source_url: str = ""
    policy: Dict[str, Any] = {}
    cost: Dict[str, float] = {"llm": 0.0, "tts": 0.0, "image": 0.0, "video": 0.0, "total": 0.0}
    error: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Job(BaseDocument):
    type: str = ""
    ref_id: str = ""
    label: str = ""
    payload: Dict[str, Any] = {}
    status: str = "queued"
    priority: int = 2
    progress: int = 0
    stage: str = ""
    error: str = ""
    worker: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class SocialComment(BaseDocument):
    platform: str = ""
    story_id: str = ""
    video_id: str = ""
    comment_id: str = ""
    author: str = ""
    text: str = ""
    likes: int = 0
    triage: Dict[str, Any] = {}
    reply_text: str = ""
    posted: bool = False
    handled: bool = False
    created_at: datetime = Field(default_factory=utcnow)
