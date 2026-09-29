from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import happens down here, after Base exists, so no matter which entrypoint
# loads this first (api, worker, beat, alembic), every model gets registered on it.
from app.models import *  # noqa