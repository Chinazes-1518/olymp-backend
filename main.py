from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import update
import uvicorn
import json

import database
import routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables in database")
    async with database.engine.begin() as connection:
        await connection.run_sync(database.MainBase.metadata.create_all)
        
    print("Clearing battle status")
    async with database.sessions.begin() as session:
        await session.execute(update(database.Users).values(status=None).where(database.Users.status == 'battle'))

    if 0:
        print('Adding tasks from json')
        name = 'Математический анализ'
        with open(f'misc/{name}.json', encoding='utf8') as f:
            data = json.load(f)
        i = 0
        for record in data:
            i += 1
            print(i / len(data) * 100)
            await routes.administration.import_tasks_to_db([{
                'id': record['id'],
                'level': int(record['difficulty']),
                'category': name,
                'subcategory': list(set(record['subcategory'])),
                'condition': record['condition'],
                'solution': record['solution'],
                'answer': record['answer'],
                'source': 'problems.ru',
                'answer_type': 'string'
            }])

    yield

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
