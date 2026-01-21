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
    
    print('Adding tasks from json')
    with open('misc/tasks.json', encoding='utf8') as f:
        data = json.load(f)
    for record in data:
        await routes.administration.import_tasks_to_db({
            'id': record['id'],
            'level': record['difficulty'],
            'category': 'Логика и теория множеств',
            'subcategory': ['123', '456'],
            'condition': '1',
            'solution': '2',
            'answer': '3',
            'source': '4',
            'answer_type': '5'
        })
    
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
    uvicorn.run("__main__:app", host="0.0.0.0", port=8000, reload=True, workers=2)
