from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import database
# import routes
import utils
# from routes import analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables in database")
    async with database.engine.begin() as connection:
        # await connection.run(database.MyBase.metadata.drop_all)
        await connection.run_sync(database.MainBase.metadata.create_all)

    # print("Starting scheduler")
    # scheduler = AsyncIOScheduler()
    # # scheduler.add_job(analytics.update_expired_products,
    # #                   trigger=CronTrigger(hour=0, minute=0, second=0, timezone=timezone('Europe/Moscow')))
    # scheduler.start()
    # # await analytics.update_expired_products()

    yield


app = FastAPI(lifespan=lifespan)
# app.include_router(routes.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return utils.json_responce({'data': 'йоу сасло?'})

# @app.on_event("startup")
# async def startup_event():
#     start_scheduler()

# @app.on_event("shutdown")
# async def shutdown_event():
#     shutdown_scheduler()