# main.py
import os
import asyncio
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv()) 

from handlers.developer.developer_router import DeveloperRouter  

from aiogram import Dispatcher, Bot 
from aiogram.client.default import DefaultBotProperties  
from aiogram.enums.parse_mode import ParseMode 

from database.engine import create_db, drop_db, session_maker 

from middlewares.db import DataBaseSession 


from handlers.admin.admin_router import AdminRouter
from handlers.user.user_router import UserRouter 
import bot_instance 



# ======================================================================
# INITIALIZATION
# ======================================================================

# Initialize bot
bot = Bot(
    token=os.getenv("TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Initialize dispatcher
dp = Dispatcher()


# Include routers
dp.include_router(DeveloperRouter)
dp.include_router(AdminRouter)
dp.include_router(UserRouter)


# Сохраняем бота в синглтоне
bot_instance.set_bot_instance(bot)
all_user_id = []



# ======================================================================
# STARTUP/SHUTDOWN HANDLERS
# ======================================================================

async def on_startup(bot):
    """Initialize database on bot startup"""
    run_param = False   # Set to True to reset database
    if run_param:
        await drop_db()

    await create_db()
    print("✅ Database initialized")


async def on_shutdown(bot: Bot):
    """Cleanup on bot shutdown"""
    print("❌ Bot stopped")


# ======================================================================
# SCHEDULED TASKS SETUP
# ======================================================================


# ======================================================================
# MAIN BOT POLLING FUNCTION
# ======================================================================

async def polling_bot():
    """Main function to start the bot"""

    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Add database middleware
    dp.update.middleware(DataBaseSession(session_pool=session_maker))

    # Start polling
    await bot.delete_webhook(
        drop_pending_updates=True,
    )
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


# ======================================================================
# ENTRY POINT
# ======================================================================

if __name__ == "__main__":
    asyncio.run(polling_bot())