import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.core.config import load_settings
from app.core.logging import configure_logging
from app.handlers.admin import register_admin_handlers
from app.handlers.navigation import register_navigation_handlers
from app.handlers.facebook_promo_chat import register_facebook_promo_chat
from app.services.automation_runner import AutomationRunner
from app.services.bootstrap import bootstrap_dependencies
from app.services.schedule_runner import ScheduleRunner


async def run() -> None:
    configure_logging()
    settings = load_settings()
    dependencies = bootstrap_dependencies(settings)

    if not settings.bot_token:
        logging.info("BOT_TOKEN is not set yet; bootstrap completed without starting polling.")
        return

    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(register_admin_handlers(dependencies["context"]))
    dispatcher.include_router(register_facebook_promo_chat(dependencies["context"]))
    dispatcher.include_router(register_navigation_handlers(dependencies["context"]))
    schedule_runner = ScheduleRunner(dependencies["context"], bot)
    automation_runner = AutomationRunner(dependencies["context"], bot)
    await schedule_runner.start()
    await automation_runner.start()

    logging.info("Starting polling for everithing_manager in %s mode", settings.app_env)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await automation_runner.stop()
        await schedule_runner.stop()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
