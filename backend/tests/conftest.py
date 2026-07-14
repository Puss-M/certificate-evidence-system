"""
pytest 测试专用的数据库 fixture。

之前 students/certificates/verification 这几个接口都是纯 mock 数据，测试不需要真实数据库。
这次把证书生成、验真接口换成真实读写数据库之后，测试也需要一个可用的数据库——这里用内存
SQLite，不依赖本机是否装了 MySQL、也不会污染真实数据库，每个测试函数结束后自动清空。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  确保所有模型都注册到 Base，建表时才认得到它们
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app


@pytest.fixture()
def db_session():
    # StaticPool 是关键：FastAPI 的同步依赖是在线程池里跑的，请求线程和这里建表
    # 用的线程不是同一个。SQLite 的 :memory: 数据库默认按连接/线程隔离，换个线程
    # 拿到的是另一个空库；StaticPool 强制全程只用同一条连接，才能跨线程共享同一份数据。
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine)
    session = testing_session_local()

    def override_get_db():
        yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        session.close()
        fastapi_app.dependency_overrides.pop(get_db, None)
