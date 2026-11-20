from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionDep, violated_constraint
from app.models import Club, Event, Registration, Room, User
from app.schemas import (
    ErrorResponse,
    EventCreate,
    EventPage,
    EventRead,
    EventUpdate,
    RegistrationRead,
)

router = APIRouter(prefix="/api/events", tags=["Мероприятия"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Мероприятие не найдено"}}
CONFLICT = {
    409: {
        "model": ErrorResponse,
        "description": "Нарушено бизнес-правило или конфликт записи",
    }
}

TOMSK = timezone(timedelta(hours=7))
ACTIVE = ("pending", "published")


def get_event_or_404(session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Мероприятие не найдено")
    return event


def free_seats_expression():
    active_count = (
        select(func.count(Registration.id))
        .where(
            Registration.event_id == Event.id,
            Registration.status == "active",
        )
        .correlate(Event)
        .scalar_subquery()
    )
    return (Event.capacity - active_count).label("free_seats")


def event_read_query(event_id: int):
    return select(Event, free_seats_expression()).where(Event.id == event_id)


def to_event_read(event: Event, free_seats: int) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "club_id": event.club_id,
        "room_id": event.room_id,
        "starts_at": event.starts_at,
        "ends_at": event.ends_at,
        "capacity": event.capacity,
        "free_seats": int(free_seats),
    }


def get_event_read_or_404(session, event_id: int) -> dict:
    row = session.execute(event_read_query(event_id)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Мероприятие не найдено")
    event, free_seats = row
    return to_event_read(event, free_seats)


def check_business_rules(session, data: dict, event_id: int | None = None) -> Club:
    club = session.get(Club, data["club_id"])
    if club is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Клуба {data['club_id']} нет")

    room = session.get(Room, data["room_id"])
    if room is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Аудитории {data['room_id']} нет"
        )

    if data["capacity"] > room.capacity:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Аудитория «{room.name}» вмещает {room.capacity} человек, а указано {data['capacity']}",
        )

    query = select(Event).where(
        Event.room_id == data["room_id"],
        Event.status.in_(ACTIVE),
        Event.starts_at < data["ends_at"],
        Event.ends_at > data["starts_at"],
    )
    if event_id is not None:
        query = query.where(Event.id != event_id)

    other = session.scalars(query.limit(1)).first()
    if other is not None:
        start = other.starts_at.astimezone(TOMSK)
        end = other.ends_at.astimezone(TOMSK)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Аудитория «{room.name}» занята: {other.title}, {start:%d.%m %H:%M}–{end:%H:%M}",
        )
    return club


def commit_or_409(session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if violated_constraint(exc) == "events_room_no_overlap":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Аудиторию только что заняли на это время",
            ) from exc
        raise


@router.get("", response_model=EventPage, summary="Афиша")
def list_events(
    session: SessionDep,
    club_id: Annotated[int | None, Query(description="Только мероприятия этого клуба")] = None,
    date_from: Annotated[
        date | None, Query(description="Начиная с даты, включительно")
    ] = None,
    date_to: Annotated[
        date | None, Query(description="По дату, включительно")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    size: Annotated[
        int, Query(ge=1, le=100, description="Мероприятий на странице")
    ] = 20,
):
    query = select(Event, free_seats_expression()).where(Event.status == "published")

    if club_id is not None:
        query = query.where(Event.club_id == club_id)
    if date_from is not None:
        query = query.where(
            Event.starts_at >= datetime.combine(date_from, time.min, TOMSK)
        )
    if date_to is not None:
        next_day = date_to + timedelta(days=1)
        query = query.where(
            Event.starts_at < datetime.combine(next_day, time.min, TOMSK)
        )

    total = session.scalar(
        select(func.count()).select_from(query.with_only_columns(Event.id).subquery())
    )

    rows = session.execute(
        query.order_by(Event.starts_at, Event.id)
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    items = [to_event_read(event, free_seats) for event, free_seats in rows]
    return {"items": items, "total": total, "page": page, "size": size}


@router.get(
    "/{event_id}",
    response_model=EventRead,
    responses=NOT_FOUND,
    summary="Одно мероприятие",
)
def get_event(event_id: int, session: SessionDep):
    return get_event_read_or_404(session, event_id)


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    responses=CONFLICT,
    summary="Создать мероприятие",
)
def create_event(payload: EventCreate, session: SessionDep):
    data = payload.model_dump()
    club = check_business_rules(session, data)

    if not club.organizers:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "У клуба нет организатора",
        )

    event = Event(**data, author=club.organizers[0])
    session.add(event)
    commit_or_409(session)
    session.refresh(event)
    return to_event_read(event, 0)


@router.patch(
    "/{event_id}",
    response_model=EventRead,
    responses={**NOT_FOUND, **CONFLICT},
    summary="Изменить мероприятие",
)
def update_event(event_id: int, payload: EventUpdate, session: SessionDep):
    event = get_event_or_404(session, event_id)
    current = {
        name: getattr(event, name)
        for name in EventCreate.model_fields
    }
    merged = {**current, **payload.model_dump(exclude_unset=True)}

    try:
        checked = EventCreate.model_validate(merged).model_dump()
    except ValidationError as exc:
        errors = exc.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, errors
        ) from exc

    check_business_rules(session, checked, event_id=event_id)

    for name, value in checked.items():
        setattr(event, name, value)

    commit_or_409(session)
    return get_event_read_or_404(session, event_id)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    summary="Удалить мероприятие",
)
def delete_event(event_id: int, session: SessionDep):
    session.delete(get_event_or_404(session, event_id))
    session.commit()


@router.post(
    "/{event_id}/registrations/{user_id}",
    response_model=RegistrationRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse, "description": "Мероприятие или студент не найден"},
        409: {"model": ErrorResponse, "description": "Нет свободных мест или запись уже существует"},
    },
    summary="Записать студента на мероприятие",
)
def register_user(event_id: int, user_id: int, session: SessionDep):
    event = get_event_or_404(session, event_id)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")

    if event.status != "published":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Записаться можно только на опубликованное мероприятие",
        )

    if event.starts_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Мероприятие уже началось",
        )

    existing = session.scalar(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.user_id == user_id,
            Registration.status == "active",
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Студент уже записан")

    active_count = session.scalar(
        select(func.count())
        .select_from(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.status == "active",
        )
    )

    if active_count >= event.capacity:
        raise HTTPException(status.HTTP_409_CONFLICT, "Свободных мест нет")

    registration = session.scalar(
        select(Registration)
        .where(
            Registration.event_id == event_id,
            Registration.user_id == user_id,
        )
    )
    if registration is None:
        registration = Registration(
            event_id=event_id,
            user_id=user_id,
            status="active",
        )
        session.add(registration)
    else:
        registration.status = "active"

    try:
        session.commit()
        session.refresh(registration)
    except IntegrityError as exc:
        session.rollback()
        if violated_constraint(exc) == "registrations_one_active":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Студент уже записан",
            ) from exc
        raise

    return registration


@router.delete(
    "/{event_id}/registrations/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Активная запись не найдена",
        },
        409: {
            "model": ErrorResponse,
            "description": "Мероприятие уже началось",
        },
    },
    summary="Отменить запись",
)
def cancel_registration(event_id: int, user_id: int, session: SessionDep):
    event = get_event_or_404(session, event_id)

    if event.starts_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Мероприятие уже началось",
        )

    registration = session.scalar(
        select(Registration).where(
            Registration.event_id == event_id,
            Registration.user_id == user_id,
            Registration.status == "active",
        )
    )
    if registration is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Активная запись не найдена")

    registration.status = "cancelled"
    session.commit()
