"""
db_config.py
============
프로젝트 전역 MySQL 접속 설정 헬퍼.

우선순위
--------
1. 환경변수 (MYSQL_HOST / MYSQL_PORT / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE)
2. Streamlit secrets ([mysql] 섹션) — Streamlit 실행 환경에서만
3. 아래 DEFAULTS

사용 예
-------
    from db_config import get_connection, get_engine, get_config

    conn = get_connection()          # pymysql 커넥션 (스크립트용)
    engine = get_engine()            # SQLAlchemy 엔진 (pandas.read_sql 용)
"""

from __future__ import annotations

import os

import pymysql

try:
    from dotenv import load_dotenv

    load_dotenv()  # .env 파일이 있으면 MYSQL_* 환경변수로 로드 (팀 저장소 컨벤션)
except Exception:
    pass

DEFAULTS = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1234",
    "database": "car_bti",
    "charset": "utf8mb4",
}


def _from_streamlit_secrets() -> dict:
    """Streamlit secrets([mysql])에서 값 읽기. 파일이 없으면 접근하지 않음
    (없는 상태에서 st.secrets에 접근하면 'No secrets files found' 안내가 출력됨)."""
    secrets_paths = [
        os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml"),
    ]
    if not any(os.path.exists(p) for p in secrets_paths):
        return {}

    try:
        import streamlit as st  # noqa: PLC0415

        if "mysql" in st.secrets:
            section = st.secrets["mysql"]
            return {k: section[k] for k in section}
    except Exception:
        pass
    return {}


def get_config() -> dict:
    """현재 적용될 MySQL 접속 설정 dict 반환."""
    cfg = dict(DEFAULTS)
    cfg.update(_from_streamlit_secrets())

    env_map = {
        "host": "MYSQL_HOST",
        "port": "MYSQL_PORT",
        "user": "MYSQL_USER",
        "password": "MYSQL_PASSWORD",
        "database": "MYSQL_DATABASE",
    }
    for key, env in env_map.items():
        val = os.environ.get(env)
        if val is not None and val != "":
            cfg[key] = val

    cfg["port"] = int(cfg["port"])
    return cfg


def get_connection(use_database: bool = True):
    """pymysql 커넥션 반환. use_database=False면 DB 미지정(최초 DB 생성용)."""
    cfg = get_config()
    kwargs = dict(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        charset=cfg.get("charset", "utf8mb4"),
    )
    if use_database:
        kwargs["database"] = cfg["database"]
    return pymysql.connect(**kwargs)


def ensure_database() -> None:
    """car_bti 데이터베이스가 없으면 생성."""
    cfg = get_config()
    conn = get_connection(use_database=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def get_sqlalchemy_url(hide_password: bool = False) -> str:
    cfg = get_config()
    pw = "***" if hide_password else cfg["password"]
    return (
        f"mysql+pymysql://{cfg['user']}:{pw}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}?charset=utf8mb4"
    )


def get_engine():
    """SQLAlchemy 엔진 반환 (pandas.read_sql 권장). 미설치 시 ImportError."""
    from sqlalchemy import create_engine  # noqa: PLC0415

    return create_engine(get_sqlalchemy_url(), pool_recycle=3600)
