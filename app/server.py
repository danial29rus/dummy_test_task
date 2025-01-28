from datetime import datetime

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column


class DeploySettings(BaseSettings):

    env_file: str = "deploy/.env"

    model_config = SettingsConfigDict(env_file=env_file, extra="ignore")


class DBSettings(DeploySettings):
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    @property
    def POSTGRES_URL(self):
        _user = self.POSTGRES_USER
        _password = self.POSTGRES_PASSWORD
        _host = self.POSTGRES_HOST
        _port = self.POSTGRES_PORT
        _db = self.POSTGRES_DB
        url = f"postgresql+asyncpg://{_user}:{_password}@{_host}:{_port}/{_db}"
        return url


db_settings = DBSettings()


engine: AsyncEngine = create_async_engine(db_settings.POSTGRES_URL, echo=False)

async_session = async_sessionmaker(
    bind=engine, expire_on_commit=False, autoflush=True, future=True
)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    last_msg_num: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    sender_name: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_msg_num: Mapped[int] = mapped_column(Integer, nullable=False)

    # Уникальный индекс на (sender_name, user_msg_num),
    # чтобы не допустить дублирования счётчика сообщений у одного пользователя.
    __table_args__ = (
        UniqueConstraint(
            "sender_name", "user_msg_num", name="uq_sender_msgnum"
        ),
    )


class MessageRequest(BaseModel):
    sender_name: str
    text: str


class MessageResponse(BaseModel):
    message_id: int
    sender_name: str
    text: str
    created_at: datetime
    user_msg_num: int


class MessagesListResponse(BaseModel):
    messages: list[MessageResponse]


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


app = FastAPI()


@app.post("/messages/", response_model=MessagesListResponse)
async def post_message(
    msg: MessageRequest,
    db: AsyncSession = Depends(get_db),
):
    # Оборачиваем логику в транзакцию, чтобы все операции были атомарными,
    # включая блокировку записи пользователя (FOR UPDATE).
    async with db.begin():
        # Ищем пользователя в таблице users c блокировкой FOR UPDATE
        result = await db.execute(
            select(User)
            .where(User.username == msg.sender_name)
            .with_for_update()
        )
        user = result.scalar_one_or_none()

        if user is None:
            # Если такого пользователя ещё нет, создаём
            user = User(username=msg.sender_name, last_msg_num=0)
            db.add(user)
            await db.flush()  # нужно, чтобы user.id сформировалось

        # Увеличиваем счётчик сообщений пользователя
        user.last_msg_num += 1
        user_msg_counter = user.last_msg_num

        # Создаём новое сообщение
        new_message = Message(
            sender_name=msg.sender_name,
            text=msg.text,
            user_msg_num=user_msg_counter,
        )
        db.add(new_message)
        await db.flush()  # нужно, чтобы message_id у new_message сформировался

        # Теперь получаем последние 10 сообщений, включая текущее.
        # Текущее сообщение имеет message_id = new_message.message_id
        # Ограничим выборку по message_id <= этого значения, чтобы
        # не включать в ответ сообщения, пришедшие "позже"
        # в параллельных запросах.
        last_10_stmt = (
            select(Message)
            .where(Message.message_id <= new_message.message_id)
            .order_by(Message.message_id.desc())
            .limit(10)
        )
        last_10_result = await db.execute(last_10_stmt)
        last_10_messages = last_10_result.scalars().all()

    result = MessagesListResponse(
        messages=[
            MessageResponse(
                message_id=m.message_id,
                sender_name=m.sender_name,
                text=m.text,
                created_at=m.created_at,
                user_msg_num=m.user_msg_num,
            )
            for m in last_10_messages
        ]
    )
    return result
