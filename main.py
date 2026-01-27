from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import json

import database
import routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables in database")
    async with database.engine.begin() as connection:
        await connection.run_sync(database.MainBase.metadata.create_all)
    # await routes.analytics.change_values(4, {'task_quantity': 3, 'answer_quantity': 5, 'time_per_task': {'123456': 180}})

    # print('Adding tasks from json')
    # name = 'Геометрия'
    # with open(f'misc/{name}.json', encoding='utf8') as f:
    #     data = json.load(f)
    # for record in data[:50]:
    #     await routes.administration.import_tasks_to_db({
    #         'id': record['id'],
    #         'level': int(record['difficulty']),
    #         'category': name,
    #         'subcategory': list(set(record['subcategory'])),
    #         'condition': record['condition'],
    #         'solution': record['solution'],
    #         'answer': record['answer'],
    #         'source': 'problems.ru',
    #         'answer_type': 'string'
    #     })

    yield

# {
#     'task_quantity': 1,
#     'answer_quantity': 1,
#     'time_per_task': {
#         123456: 180
#     }
# }

app = FastAPI(lifespan=lifespan)
app.include_router(routes.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=['test_websocket.py'],
        workers=2)
