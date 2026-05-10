import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, JSON, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base
from models.agent import now_utc


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    graph_definition: Mapped[dict] = mapped_column(JSON, default=lambda: {"nodes": [], "edges": []})
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, onupdate=now_utc)
