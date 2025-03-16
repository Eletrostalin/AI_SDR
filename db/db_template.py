import logging
from db.db import SessionLocal
from db.models import Templates, Waves, Company, CompanyInfo, ContentPlan, Campaigns, ChatThread
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


def get_campaign_by_thread(thread_id):
    """ Получает кампанию по thread_id, если она есть """
    db = SessionLocal()
    try:
        campaign = db.query(Campaigns).filter(Campaigns.thread_id == thread_id).first()
        if not campaign:
            logger.warning(f"Кампания не найдена для thread_id={thread_id} или удалена")
        return campaign
    except SQLAlchemyError as e:
        logger.error(f"Ошибка в get_campaign_by_thread: {e}", exc_info=True)
        return None
    finally:
        db.close()


def get_company_by_id(company_id):
    """ Получает информацию о компании по company_id с подгрузкой CompanyInfo """
    db = SessionLocal()
    try:
        company = db.query(Company).options(joinedload(Company.company_info)).filter_by(company_id=company_id).first()
        if not company:
            logger.warning(f"Компания не найдена для company_id={company_id}")
        return company
    finally:
        db.close()


def get_chat_thread_by_chat_id(chat_id):
    """ Получает чат-потоки (ChatThread) по chat_id """
    db = SessionLocal()
    try:
        threads = db.query(ChatThread).filter_by(chat_id=chat_id).all()
        if not threads:
            logger.warning(f"ChatThread не найден для chat_id={chat_id}")
        return threads  # Возвращаем список потоков
    finally:
        db.close()


def get_waves_by_content_plan(content_plan_id):
    """ Получает все волны для заданного контентного плана """
    db = SessionLocal()
    try:
        waves = db.query(Waves).filter_by(content_plan_id=content_plan_id).all()
        if not waves:
            logger.warning(f"Нет волн для контентного плана content_plan_id={content_plan_id}")
        return waves
    finally:
        db.close()


def get_wave_by_id(wave_id):
    """ Получает одну волну по ее ID """
    db = SessionLocal()
    try:
        wave = db.query(Waves).filter_by(wave_id=wave_id).first()
        if not wave:
            logger.warning(f"Волна с wave_id={wave_id} не найдена")
        return wave
    finally:
        db.close()


def get_content_plans_by_campaign(campaign_id):
    """ Получает все контент-планы для заданной кампании """
    db = SessionLocal()
    try:
        content_plans = db.query(ContentPlan).filter_by(campaign_id=campaign_id).all()
        if not content_plans:
            logger.warning(f"Нет контент-планов для campaign_id={campaign_id}")
        return content_plans
    finally:
        db.close()


def get_content_plan_by_id(content_plan_id):
    """ Получает контент-план по его ID """
    db = SessionLocal()
    try:
        content_plan = db.query(ContentPlan).filter_by(content_plan_id=content_plan_id).first()
        if not content_plan:
            logger.warning(f"Контент-план с content_plan_id={content_plan_id} не найден")
        return content_plan
    finally:
        db.close()


def get_company_info_and_content_plan(company_id, content_plan_id):
    """ Получает информацию о компании и описание контент-плана """
    db = SessionLocal()
    try:
        company_info = db.query(CompanyInfo).filter_by(company_id=company_id).first()
        content_plan = db.query(ContentPlan).filter_by(content_plan_id=content_plan_id).first()

        if not company_info or not content_plan:
            logger.warning(f"Данные компании или контент-план не найдены: company_id={company_id}, content_plan_id={content_plan_id}")

        return company_info, content_plan.description if content_plan else None
    finally:
        db.close()


def save_template(company_id, campaign_id, wave_id, template_content, user_request, subject):
    """ Сохраняет шаблон в БД и возвращает объект шаблона """
    db = SessionLocal()
    try:
        new_template = Templates(
            company_id=company_id,
            campaign_id=campaign_id,
            wave_id=wave_id,
            template_content=template_content,
            user_request=user_request,
            subject=subject,
        )
        db.add(new_template)
        db.commit()
        logger.info(f"Шаблон успешно сохранен: template_id={new_template.template_id}")
        return new_template
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка при сохранении шаблона: {e}", exc_info=True)
        return None
    finally:
        db.close()