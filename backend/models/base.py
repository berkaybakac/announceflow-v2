from sqlalchemy import Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Tum modellerin miras aldigi SQLAlchemy 2.0 base sinifi."""

    pass


class IdMixin:
    """Integer PK saglayan mixin. prayer_times haric tum tablolar kullanir."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
