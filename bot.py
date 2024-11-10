from chat_handlers import router as chat_router

def setup_routers(dp):
    """
    Настраивает маршрутизаторы, подключая обработчики для чата с пользователями
    и для команд администратора.
    """
    dp.include_router(chat_router)  # Обработчик для сообщений в общем чате