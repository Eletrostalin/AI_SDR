import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session
from db.models import Waves, Templates
from db.db_draft import generate_drafts_for_wave
from utils.google_doc import append_drafts_to_sheet

@pytest.mark.asyncio
async def test_generate_drafts_for_wave(mocker):
    """Тестирует процесс генерации черновиков и их добавления в Google Таблицу."""

    # 🔹 Мокируем сессию БД
    db_mock = mocker.MagicMock(spec=Session)

    # 🔹 Создаем тестовую волну
    test_wave = Waves(
        wave_id=1,
        content_plan_id=10,
        campaign_id=100,
        company_id=200,
        send_date=None,  # Дата не важна для теста
        subject="Тестовая тема письма"
    )

    # 🔹 Создаем тестовый шаблон письма
    test_template = Templates(
        content_plan_id=10,
        text="Добрый день, {company_name}! У нас есть предложение..."
    )

    # 🔹 Мокируем получение шаблона
    db_mock.query().filter_by().first.return_value = test_template

    # 🔹 Создаем тестовые данные лидов
    test_leads = pd.DataFrame([
        {"email": "test1@example.com", "company_name": "Компания 1"},
        {"email": "test2@example.com", "company_name": "Компания 2"},
    ])

    # 🔹 Мокируем `append_drafts_to_sheet`, чтобы не отправлять реальные данные в Google
    append_mock = mocker.patch("utils.google_doc.append_drafts_to_sheet", return_value=None)

    # 🔹 Запускаем генерацию черновиков
    await generate_drafts_for_wave(db_mock, test_leads, test_wave)

    # 🔹 Проверяем, что `append_drafts_to_sheet` вызвался
    append_mock.assert_called_once()

    # 🔹 Проверяем, что записанные данные корректны
    saved_drafts = append_mock.call_args[0][2]  # Аргумент с данными черновиков

    assert len(saved_drafts) == 2  # Должно быть 2 черновика
    assert saved_drafts[0]["email"] == "test1@example.com"
    assert saved_drafts[1]["email"] == "test2@example.com"
    assert saved_drafts[0]["subject"] == "Тестовая тема письма"  # Проверяем тему
    assert "Добрый день" in saved_drafts[0]["text"]  # Проверяем текст письма