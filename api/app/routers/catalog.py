from fastapi import APIRouter, Body, HTTPException, Path, status

from app import storage
from app.schemas import Club, ClubCreate, ErrorResponse, Room

router = APIRouter(prefix="/api", tags=["Справочники"])


@router.get("/clubs", response_model=list[Club], summary="Клубы")
def list_clubs():
    return list(storage.CLUBS.values())


@router.get(
    "/clubs/{club_id}",
    response_model=Club,
    responses={404: {"model": ErrorResponse, "description": "Клуб не найден"}},
    summary="Один клуб",
    description="Возвращает клуб по его идентификатору.",
)
def get_club(club_id: int):
    club = storage.CLUBS.get(club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клуб не найден")
    return club


@router.post(
    "/clubs",
    response_model=Club,
    status_code=status.HTTP_201_CREATED,
    summary="Создать клуб",
    description="Создаёт клуб. Название очищается от пробелов по краям и должно быть уникальным без учёта регистра.",
    responses={
        409: {"model": ErrorResponse, "description": "Клуб с таким названием уже существует"},
        422: {"model": ErrorResponse, "description": "Название должно содержать от 2 до 100 символов"},
    },
)
def create_club(payload: ClubCreate):
    normalized_name = payload.name
    for club in storage.CLUBS.values():
        if club["name"].casefold() == normalized_name.casefold():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Клуб с таким названием уже существует",
            )

    club = {"id": storage.next_club_id(), "name": normalized_name}
    storage.CLUBS[club["id"]] = club
    return club


@router.patch(
    "/clubs/{club_id}",
    response_model=Club,
    summary="Переименовать клуб",
    description="Изменяет название существующего клуба. Пробелы по краям обрезаются, регистр при проверке уникальности не учитывается.",
    responses={
        404: {"model": ErrorResponse, "description": "Клуб не найден"},
        409: {"model": ErrorResponse, "description": "Клуб с таким названием уже существует"},
        422: {"model": ErrorResponse, "description": "Название должно содержать от 2 до 100 символов"},
    },
)
def rename_club(
    club_id: int = Path(description="Идентификатор клуба", examples=[1]),
    payload: ClubCreate = Body(...),
):
    club = storage.CLUBS.get(club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клуб не найден")

    for other in storage.CLUBS.values():
        if other["id"] != club_id and other["name"].casefold() == payload.name.casefold():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Клуб с таким названием уже существует",
            )

    club["name"] = payload.name
    return club


@router.delete(
    "/clubs/{club_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить клуб",
    description="Удаляет клуб, только если с ним не связано ни одного мероприятия.",
    responses={
        404: {"model": ErrorResponse, "description": "Клуб не найден"},
        409: {"model": ErrorResponse, "description": "У клуба есть связанные мероприятия"},
        422: {"model": ErrorResponse, "description": "Некорректный идентификатор клуба"},
    },
)
def delete_club(
    club_id: int = Path(description="Идентификатор клуба", examples=[3]),
):
    club = storage.CLUBS.get(club_id)
    if club is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клуб не найден")

    events_count = sum(1 for event in storage.EVENTS.values() if event["club_id"] == club_id)
    if events_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Нельзя удалить клуб: с ним связано мероприятий: {events_count}",
        )

    del storage.CLUBS[club_id]
    return None


@router.get("/rooms", response_model=list[Room], summary="Аудитории")
def list_rooms():
    return list(storage.ROOMS.values())
