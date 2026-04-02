from fastapi import FastAPI

from .routes.api import router

app = FastAPI(
    title='EIME Intent Modeling Engine',
    description='Backend for ACRE / EIME dual execution reasoning platform',
    version='0.1.0',
)

app.include_router(router, prefix='', tags=['analysis'])
