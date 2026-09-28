from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import after Base is defined so every model registers its table on this metadata,
# regardless of which entrypoint (api, celery worker, celery beat, alembic) loads this module first.
from app.models import *  # noqa