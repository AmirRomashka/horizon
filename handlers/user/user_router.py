"""
User Router Module
==================

This module serves as the central entry point for all user-related routers.
All user-facing functionality is imported and registered here for clean organization.

Module Structure:
-----------------
1. User Profile - Profile viewing and tariff selection
2. User Payment - Payment processing and subscription activation
3. User Support - Help and support functionality

Usage:
------
The UserRouter is imported in main.py and included in the dispatcher.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from aiogram import Router

from handlers.user.user_profile import UserProfileRouter
from handlers.user.user_payment import UserPaymentRouter

# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

UserRouter = Router(name="user_router")

"""
Main user router that aggregates all user-facing functionality.

This router is included in the main dispatcher and handles:
- User profile viewing
- Tariff selection and purchase
- Payment processing via YooKassa
- Subscription activation
- Help and support
"""

# =============================================================================
# ROUTER REGISTRATION
# =============================================================================

UserRouter.include_routers(
    UserProfileRouter,
    UserPaymentRouter,
)

# =============================================================================
# USAGE EXAMPLE
# =============================================================================

"""
How to use in main.py:
---------------------
from handlers.user.user_router import UserRouter

dp.include_router(UserRouter)

All user functionality is now available under the UserRouter.
Each sub-router handles its own callbacks and states.

User Flow:
----------
1. User starts bot -> sees profile with available tariffs
2. User clicks on tariff -> UserPaymentRouter handles buy_rate_{id}
3. User confirms payment -> payment created via YooKassa
4. Payment succeeds -> subscription created, VLESS link sent

State Structure:
----------------
User states are defined in States/user_states.py:
- UserStates.buy_subscription: tariff selection
- UserStates.payment_waiting: waiting for phone (optional)
- UserStates.subscription_confirm: subscription confirmation
- UserStates.support_message: support request
"""