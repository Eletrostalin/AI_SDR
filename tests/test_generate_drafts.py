import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch
from sqlalchemy.orm import Session
from db.models import Waves, Templates
from db.db_draft import generate_drafts_for_wave, generate_draft_for_lead
from utils.google_doc import append_drafts_to_sheet
from utils.utils import send_to_model

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
        {"lead_id": 1, "email": "test1@example.com", "company_name": "Компания 1"},
        {"lead_id": 2, "email": "test2@example.com", "company_name": "Компания 2"},
    ])

    # 🔹 Мокируем send_to_model (чтобы избежать реальных вызовов модели)
    mocker.patch("utils.utils.send_to_model", new=AsyncMock(return_value="Сгенерированное письмо"))

    # 🔹 Мокируем generate_draft_for_lead, чтобы избежать реальных генераций
    mock_generate_draft = mocker.patch("db.db_draft.generate_draft_for_lead", new=AsyncMock())
    mock_generate_draft.side_effect = lambda template, lead, subject, wave_id: {
        "wave_id": wave_id,
        "lead_id": lead["lead_id"],
        "email": lead["email"],
        "company_name": lead["company_name"],
        "subject": subject,
        "text": "Сгенерированное письмо"
    }

    # 🔹 Мокируем append_drafts_to_sheet, чтобы данные не отправлялись в Google
    append_mock = mocker.patch("utils.google_doc.append_drafts_to_sheet", return_value=None)

    # 🔹 Запускаем генерацию черновиков
    await generate_drafts_for_wave(db_mock, test_leads, test_wave)

    # 🔹 Проверяем, что `generate_draft_for_lead` вызвался 2 раза (по числу лидов)
    assert mock_generate_draft.call_count == 2

    # 🔹 Проверяем, что `append_drafts_to_sheet` вызвался
    append_mock.assert_called_once()

    # 🔹 Проверяем, что записанные данные корректны
    saved_drafts = append_mock.call_args[0][2]  # Аргумент с данными черновиков

    assert len(saved_drafts) == 2  # Должно быть 2 черновика
    assert saved_drafts[0]["email"] == "test1@example.com"
    assert saved_drafts[1]["email"] == "test2@example.com"
    assert saved_drafts[0]["subject"] == "Тестовая тема письма"  # Проверяем тему
    assert "Сгенерированное письмо" in saved_drafts[0]["text"]  # Проверяем текст письма