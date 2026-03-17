import logging
from sqlalchemy import insert
from sqlalchemy.orm import sessionmaker

from models import SqlQueryLog

logger = logging.getLogger("sql_logger_worker")


def process_sql_log(record, app=None):
    """
    Fonction appelée :
    - directement en dev (thread)
    - via RQ en prod
    """

    if app:
        ctx = app.app_context()
        ctx.push()

    try:
        from yourapp import db  # import lazy pour éviter circular deps

        Session = sessionmaker(bind=db.engine)
        session = Session()

        try:
            stmt = insert(SqlQueryLog).values(**record["db"])
            session.execute(stmt)
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"DB insert failed: {e}")

        finally:
            session.close()

        try:
            logger.log(record["level"], record["message"])
        except Exception as e:
            logger.error(f"File log failed: {e}")

    finally:
        if app:
            ctx.pop()
