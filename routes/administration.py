from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, insert, or_, and_, update
from typing import Annotated
from pydantic import BaseModel
from fastapi.security import APIKeyHeader
from fastapi.params import Depends
import database
import utils

router = APIRouter(prefix='/admin')
API_Key_Header = APIKeyHeader(name='Authorization', auto_error=True)


@router.get('/statistics')
async def get_statistics(token: str = Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            request = await session.execute(select(database.BattleHistory))
        else:
            request = await session.execute(select(database.BattleHistory).where(
                or_(database.BattleHistory.id1 == user.id, database.BattleHistory.id2 == user.id)
            ))
        history = request.scalars().all()
        history_list = []
        for battle in history:
            battle_dict = {
                'id': battle.id,
                'id1': battle.id1,
                'id2': battle.id2,
                'date': battle.date.isoformat() if battle.date else None,
                'data': battle.data or {}
            }
            history_list.append(battle_dict)
        return utils.json_response({'history': history_list})


class Task(BaseModel):
    Userid: int
    level: int
    points: int
    category: str
    subcategory: list[str]
    condition: str
    solution: str
    answer: str
    source: str
    answer_type: str


@router.post('/change_role')
async def change_role(role: str, user_id: int, token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            await session.execute(update(database.Users).where(database.Users.id == user_id).values(role=role))
        else:
            raise HTTPException(403, {'error': 'нужны права администратора!'})


@router.get('/get_all_users')
async def get_all_users(token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            data = (await session.execute(select(database.Users))).scalars().all()
            return utils.json_response([
                {
                    'id': x.id,
                    'role': x.role,
                    'points': x.points,
                    'name': x.name,
                    'surname': x.surname,
                    'status': x.status,
                    'blocked': x.blocked
                } for x in sorted(data, key=lambda i: i.id)
            ])
        else:
            raise HTTPException(403, {'error': 'нужны права администратора!'})


@router.post('/import_task')
async def import_task(data: Task, token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            await import_tasks_to_db([data])
        else:
            raise HTTPException(403, {'error': 'Импортировать задачи может только администратор!'})


@router.post('/import_tasks')
async def import_tasks(data: list[Task], token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': "Неверный токен"})
        if user.role == 'administrator':
            await import_tasks_to_db(data)
        else:
            raise HTTPException(403, {'error': 'Импортировать задачи может только администратор!'})


@router.post('/export_tasks')
async def export_tasks(token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            request = await session.execute(select(database.Tasks))
            tasks = request.scalars().all()
            tasks_data = [{"id": item.id,
                           'level': item.level,
                           'category': item.category,
                           'subcategory': ';'.join(item.subcategory),
                           'condition': item.condition,
                           'solution': item.solution,
                           'answer': item.answer,
                           'source': item.source,
                           'answer_type': item.answer_type,
                           } for item in tasks]
            return utils.json_response({'tasks': tasks_data})
        else:
            raise HTTPException(403, {'error': ' Экспортировать задачи может только администратор!'})


async def import_tasks_to_db(data):
    async with database.sessions.begin() as session:
        cat = (await session.execute(select(database.Categories).where(database.Categories.name == data['category']))).scalar_one_or_none()
        if cat is None:
            cat_id = (await session.execute(insert(database.Categories).values(name=data['category']))).inserted_primary_key[0]
        else:
            cat_id = cat.id
        subcat_id = []
        for c in data['subcategory']:
            cat = (await session.execute(select(database.SubCategories).where(and_(database.SubCategories.name == c, database.SubCategories.category_id == cat_id)))).scalar_one_or_none()
            if cat is None:
                subcat_id.append((await session.execute(insert(database.SubCategories).values(name=c, category_id=cat_id))).inserted_primary_key[0])
            else:
                subcat_id.append(cat.id)
        data['category'] = cat_id
        data['subcategory'] = subcat_id
        if (await session.execute(select(database.Tasks).where(database.Tasks.id == int(data['id'])))).scalar_one_or_none() != None:
            print(f'task {data["id"]} already exists')
            await session.commit()
            return
        await session.execute(insert(database.Tasks), data)
        await session.commit()

@router.post('/block_user')
async def block_user(id: Annotated[int, Query()], token: str = Depends(API_Key_Header)):
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            await session.execute(
                update(database.Users).where(and_(database.Users.id == id, database.Users.role != 'administrator').values(blocked=True)))


@router.post('/unblock_user')
async def unblock_user(id: Annotated[int, Query()], token: str = Depends(API_Key_Header)):
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            await session.execute(
                update(database.Users).where(and_(database.Users.id == id, database.Users.role != 'administrator').values(blocked=False)))


