from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, insert, update
from datetime import datetime

import database


def json_response(data: dict) -> JSONResponse:
    return JSONResponse(jsonable_encoder(data), headers={
                        'Access-Control-Allow-Origin': '*'})


async def token_to_user(session, token: str) -> None:
    item = (await session.execute(select(database.Users).where(database.Users.token == token.strip()))).scalar_one_or_none()
    if item is None:
        return None
    else:
        return item


def level_to_points(level: int):
    return level * 10


def calculate_elo_rating(rating_a: int, rating_b: int, score_a: int, score_b: int,
                         k_factor: int = 32) -> tuple[int, int]:
    E_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    E_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    rating_a_1 = rating_a + k_factor * (score_a - E_a)
    rating_b_1 = rating_b + k_factor * (score_b - E_b)
    return int(rating_a_1), int(rating_b_1)


async def calculate_battle_points_and_elo(player1_id: int, player2_id: int, session,
                                          player1_correct: int, player2_correct: int,
                                          total_tasks: int, is_technical: bool = False) -> dict:

    player1 = await get_user_by_id(session, player1_id)
    player2 = await get_user_by_id(session, player2_id) if player2_id else None

    player1_rating = player1.points if player1 and hasattr(
        player1, 'points') else 1000
    player2_rating = player2.points if player2 and hasattr(
        player2, 'points') else 1000

    result = {
        'player1_id': player1_id,
        'player2_id': player2_id,
        'player1_correct': player1_correct,
        'player2_correct': player2_correct,
        'total_tasks': total_tasks,
        'is_technical': is_technical
    }

    if is_technical:
        result.update({
            'player1_new_rating': player1_rating,
            'player2_new_rating': player2_rating,
            'player1_rating_change': 0,
            'player2_rating_change': 0,
            'match_status': 'cancelled',
            'winner': None
        })
        return result

    if player1_correct > player2_correct:
        player1_score = 1.0
        winner = 'player1'
    elif player2_correct > player1_correct:
        player1_score = 0.0
        winner = 'player2'
    else:
        player1_score = 0.5
        winner = 'draw'

    player1_new, player2_new, player1_change, player2_change = await calculate_elo_rating(
        player1_rating, player2_rating, player1_score
    )

    if player1:
        await session.execute(
            update(database.Users)
            .where(database.Users.id == player1_id)
            .values(points=player1_new)
        )

    if player2:
        await session.execute(
            update(database.Users)
            .where(database.Users.id == player2_id)
            .values(points=player2_new)
        )

    await session.commit()

    result.update({
        'player1_old_rating': player1_rating,
        'player2_old_rating': player2_rating,
        'player1_new_rating': player1_new,
        'player2_new_rating': player2_new,
        'player1_rating_change': player1_change,
        'player2_rating_change': player2_change,
        'match_status': 'completed',
        'winner': winner
    })

    return result


async def save_battle_history(session, room, battle_results: dict):
    await session.execute(
        insert(database.BattleHistory).values(
            id1=room.host,
            id2=room.other if room.other else room.host,
            result1=room.game_state.player1_correct if hasattr(
                room.game_state, 'player1_correct') else 0,
            result2=room.game_state.player2_correct if hasattr(
                room.game_state, 'player2_correct') else 0,
            solvingtime1=room.game_state.player1_times if hasattr(
                room.game_state, 'player1_times') else [],
            solvingtime2=room.game_state.player2_times if hasattr(
                room.game_state, 'player2_times') and room.other else [],
            date=datetime.now(),
            status=battle_results['match_status'],
            winner=battle_results['winner']
        )
    )
    await session.commit()


async def user_by_id(session, user_id: int):
    user = await session.execute(select(database.Users).where(database.Users.id == user_id))
    return user.scalar_one_or_none()


async def get_available_tasks(session, filters: dict):
    query = select(database.Tasks)

    if 'diff_start' in filters and 'diff_end' in filters:
        query = query.where(database.Tasks.level >= int(filters['diff_start']))
        query = query.where(database.Tasks.level <= int(filters['diff_end']))

    if 'cat' in filters:
        query = query.where(database.Tasks.category == filters['cat'])

    if 'subcat' in filters and filters['subcat']:
        from sqlalchemy import cast, String
        from sqlalchemy.dialects.postgresql import ARRAY
        query = query.where(
            cast(
                database.Tasks.subcategory,
                ARRAY(String)).op('&&')(
                filters['subcat'])
        )

    if 'count' in filters:
        from sqlalchemy import func
        query = query.order_by(func.random()).limit(int(filters['count']))

    result = await session.execute(query)
    return result.scalars().all()


async def end_game_early(
        session, room, reason: str = "Game ended early", is_technical: bool = True):
    from .battle import battle_manager

    if room.game_state:
        room.game_state.status = "finished"

        player1_correct, player2_correct = room.game_state.calculate_final_points()
        battle_results = await calculate_battle_points_and_elo(
            room.host, room.other, session,
            player1_correct, player2_correct,
            len(room.game_state.task_ids),
            is_technical=is_technical
        )

        await save_battle_history(session, room, battle_results)

        await room.broadcast({
            'event': 'game_finished',
            'message': reason,
            'early': True,
            'is_technical': is_technical,
            'results': battle_results
        })

    battle_manager.remove_room(room)


async def finish_game_normal(room, session):
    game_state = room.game_state
    game_state.status = "finished"

    player1_correct, player2_correct = game_state.calculate_final_points()

    battle_results = await calculate_battle_points_and_elo(
        room.host, room.other, session,
        player1_correct, player2_correct,
        len(game_state.task_ids),
        is_technical=False
    )

    await save_battle_history(session, room, battle_results)

    player1_data = await get_user_by_id(session, room.host)
    player2_data = await get_user_by_id(session, room.other) if room.other else None

    winner_text = ""
    if battle_results['winner'] == 'player1':
        winner_text = f"{player1_data.name if player1_data else 'Player 1'} wins!"
    elif battle_results['winner'] == 'player2':
        winner_text = f"{player2_data.name if player2_data else 'Player 2'} wins!"
    else:
        winner_text = "It's a draw!"

    results_for_display = {
        'player1': {
            'name': player1_data.name if player1_data else 'Player 1',
            'surname': player1_data.surname if player1_data else '',
            'correct_answers': player1_correct,
            'total_tasks': len(game_state.task_ids),
            'old_rating': battle_results['player1_old_rating'],
            'new_rating': battle_results['player1_new_rating'],
            'rating_change': battle_results['player1_rating_change']
        },
        'player2': {
            'name': player2_data.name if player2_data else 'Player 2',
            'surname': player2_data.surname if player2_data else '',
            'correct_answers': player2_correct,
            'total_tasks': len(game_state.task_ids),
            'old_rating': battle_results['player2_old_rating'],
            'new_rating': battle_results['player2_new_rating'],
            'rating_change': battle_results['player2_rating_change']
        },
        'winner': battle_results['winner'],
        'winner_text': winner_text,
        'match_status': battle_results['match_status']
    }

    await room.broadcast({
        'event': 'game_finished',
        'message': 'Game completed!',
        'results': results_for_display
    })

    await asyncio.sleep(10)
    from .battle import battle_manager
    battle_manager.remove_room(room)
