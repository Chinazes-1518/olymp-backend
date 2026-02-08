from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy import select, update, insert, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from datetime import datetime, date, timedelta
from fastapi.security import APIKeyHeader
import database
import utils
from datetime import timedelta
from fastapi.params import Depends


router = APIRouter(prefix='/analytics')

API_Key_Header = APIKeyHeader(name='Authorization', auto_error=True)

async def create_new_record(userid: int, session: AsyncSession):
    req = await session.execute(insert(database.Analytics).values(userid=userid, date=date.today(), data={'task_quantity': 0, 'answer_quantity': 0, 'time_per_task': {}}))
    return req.inserted_primary_key[0]


async def create_battle_record(userid1: int, userid2: int, session: AsyncSession):
    req = await session.execute(insert(database.BattleHistory).values(userid1=userid1, userid2=userid2,
                                                                  data={'result1': 0, 'result2': 0, 'solving_time1': [], 'solving_time2': []},
                                                                      date=date.today()))
    return req.inserted_primary_key[0]


async def change_values(userid: int, count: dict):
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(database.Users.id == userid))
        b = request.scalar_one_or_none()
        if b is None:
            raise HTTPException(403, {'Error': 'Пользователя с таким id не существует'})
        req = await session.execute(select(database.Analytics).where(and_(database.Analytics.date == date.today(), userid == database.Analytics.userid)))
        row = req.scalar_one_or_none()
        if row is None:
            row_id = await create_new_record(userid, session)
            current = {'task_quantity': 0, 'answer_quantity': 0, 'time_per_task': {}}
        else:
            current = row.data
            row_id = row.id

        for k, v in count.items():
            if k in current:
                if k != 'time_per_task':
                     current[k] += v
                else:
                    current['time_per_task'] |= v
            else:
                if k != 'time_per_task':
                    current[k] = v
                else:
                    current['time_per_task'] |= v


        await session.execute(update(database.Analytics).where(database.Analytics.id == row_id).values(data=current))


@router.get('/get_userid_by_datetime')
async def get_userid_by_datetime(userid: int, start_date: datetime, final_date: datetime, token: str=Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        if user.role == 'administrator':
            request = await session.execute(select(database.Analytics).where(start_date <= database.Analytics.date).where(
                    database.Analytics.date <= final_date).where(database.Analytics.id==userid))
        else:
            request = await session.execute(
                select(database.Analytics).where(start_date <= database.Analytics.date).where(
                    database.Analytics.date <= final_date).where(database.Analytics.id == user.id))
        return utils.json_response(request.scalars().all())


async def add_battle_history(userid1, userid2, count):
    async with database.sessions.begin() as session:
        request = await session.execute(select(database.Users).where(and_(database.Users.id == userid1, database.Users.id == userid2)))
        b = request.scalar_one_or_none()
        if b is None:
            raise HTTPException(403, {'Error': 'Пользователей с таким id не существует'})
        req = await session.execute(select(database.BattleHistory).where(
            and_(database.BattleHistory.date == date.today(), userid1 == database.BattleHistory.id1, userid2 == database.BattleHistory.id2)))
        row = req.scalar_one_or_none()
        if row is None:
            row_id = await create_battle_record(userid1, userid2, session)
            current = {'result1': 0, 'result2': 0, 'solving_time1': [], 'solving_time2': []}
        else:
            current = row.data
            row_id = row.id

        for k, v in count.items():
            if k in current:
                if k != 'solving_time1' and k != 'solving_time2':
                    current[k] += v
                else:
                    current['solving_time1'].append(v)
                    current['solving_time2'].append(v)
            else:
                if k != 'solving_time1' and k != 'solving_time2':
                    current[k] = v
                else:
                    current['solving_time1'].append(v)
                    current['solving_time2'].append(v)

        await session.execute(update(database.BattleHistory).where(database.BattleHistory.id == row_id).values(data=current))


@router.get('/get_user_stats')
async def get_user_stats(token: str = Depends(API_Key_Header)) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        request = await session.execute(
            select(database.Analytics).where(database.Analytics.userid == user.id)
        )
        records = request.scalars().all()
        total_solved = 0
        total_attempts = 0
        total_time = 0
        time_entries = 0
        for record in records:
            data = record.data or {}
            total_solved += data.get('task_quantity', 0)
            total_attempts += data.get('answer_quantity', 0)

            time_per_task = data.get('time_per_task', {})
            if isinstance(time_per_task, dict):
                for task_time in time_per_task.values():
                    total_time += int(task_time)
                    time_entries += 1
        tasks_request = await session.execute(select(func.count(database.Tasks.id)))
        total_tasks = tasks_request.scalar() or 0
        correct_percentage = 0
        if total_attempts > 0:
            correct_percentage = round((total_solved / total_attempts) * 100, 1)
        average_time = 0
        if time_entries > 0:
            average_time = round(total_time / time_entries, 1)
        return utils.json_response({
            'total_solved': total_solved,
            'total_tasks': total_tasks,
            'total_attempts': total_attempts,
            'correct_percentage': correct_percentage,
            'average_time': average_time
        })


@router.get('/get_user_stats_by_period')
async def get_user_stats_by_period(
        start_date: str,
        end_date: str,
        token: str = Depends(API_Key_Header)
) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(400, {'error': 'Неверный формат даты. Используйте YYYY-MM-DD'})
        end_inclusive = end + timedelta(days=1)
        request = await session.execute(
            select(database.Analytics).where(
                and_(
                    database.Analytics.userid == user.id,
                    database.Analytics.date >= start,
                    database.Analytics.date < end_inclusive
                )
            )
        )
        records = request.scalars().all()
        total_solved = 0
        total_attempts = 0
        total_time = 0
        time_entries = 0
        for record in records:
            data = record.data or {}
            total_solved += data.get('task_quantity', 0)
            total_attempts += data.get('answer_quantity', 0)

            time_per_task = data.get('time_per_task', {})
            if isinstance(time_per_task, dict):
                for task_time in time_per_task.values():
                    total_time += int(task_time)
                    time_entries += 1
        tasks_request = await session.execute(select(func.count(database.Tasks.id)))
        total_tasks = tasks_request.scalar() or 0
        correct_percentage = 0
        if total_attempts > 0:
            correct_percentage = round((total_solved / total_attempts) * 100, 1)
        average_time = 0
        if time_entries > 0:
            average_time = round(total_time / time_entries, 1)
        return utils.json_response({
            'total_solved': total_solved,
            'total_tasks': total_tasks,
            'total_attempts': total_attempts,
            'correct_percentage': correct_percentage,
            'average_time': average_time
        })


@router.get('/get_user_stats_daily')
async def get_user_stats_daily(
        start_date: str,
        end_date: str,
        token: str = Depends(API_Key_Header)
) -> JSONResponse:
    async with database.sessions.begin() as session:
        user = await utils.token_to_user(session, token)
        if user is None:
            raise HTTPException(403, {'error': 'Пользователь не существует'})
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(400, {'error': 'Неверный формат даты. Используйте YYYY-MM-DD'})
        end_inclusive = end + timedelta(days=1)
        request = await session.execute(
            select(database.Analytics).where(
                and_(
                    database.Analytics.userid == user.id,
                    database.Analytics.date >= start,
                    database.Analytics.date < end_inclusive
                )
            ).order_by(database.Analytics.date)
        )
        records = request.scalars().all()
        if not records:
            return utils.json_response([])
        daily_stats = []
        for record in records:
            data = record.data or {}
            if isinstance(record.date, datetime):
                date_str = record.date.strftime('%Y-%m-%d')
            else:
                date_str = str(record.date)
            solved_tasks = data.get('task_quantity', 0)
            attempts = data.get('answer_quantity', 0)
            time_per_task = data.get('time_per_task', {})
            total_time = 0
            time_entries = 0
            if isinstance(time_per_task, dict):
                for task_time in time_per_task.values():
                    try:
                        total_time += int(task_time)
                        time_entries += 1
                    except (ValueError, TypeError):
                        continue
            average_time = 0
            if time_entries > 0:
                average_time = round(total_time / time_entries, 1)
            daily_stats.append({
                'date': date_str,
                'solved_tasks': solved_tasks,
                'attempts': attempts,
                'average_time': average_time
            })
        filled_daily_stats = []
        current_date = start
        while current_date <= end:
            date_str = current_date.strftime('%Y-%m-%d')
            stat_for_date = None
            for stat in daily_stats:
                if stat['date'] == date_str:
                    stat_for_date = stat
                    break
            if stat_for_date:
                filled_daily_stats.append(stat_for_date)
            else:
                filled_daily_stats.append({
                    'date': date_str,
                    'solved_tasks': 0,
                    'attempts': 0,
                    'average_time': 0
                })
            current_date += timedelta(days=1)
        return utils.json_response(filled_daily_stats)





