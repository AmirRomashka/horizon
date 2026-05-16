"""
Admin Router Module
===================

This module serves as the central entry point for all admin-related routers.
All admin functionality is imported and registered here for clean organization.

Module Structure:
-----------------
1. Main Panel - Admin dashboard and navigation
2. Rates Management - Tariffs CRUD
3. Hosts Management - Servers CRUD

Usage:
------
The AdminRouter is imported in main.py and included in the dispatcher.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from aiogram import Router

# -----------------------------------------------------------------------------
# Admin Modules
# -----------------------------------------------------------------------------
from handlers.admin.admin_network import AdminNetworkRouter
from handlers.admin.admin_panel import AdminPanelRouter
from handlers.admin.admin_rates import AdminRatesRouter
from handlers.admin.admin_hosts import AdminHostsRouter

# =============================================================================
# ROUTER INITIALIZATION
# =============================================================================

AdminRouter = Router(name="admin_router")


# =============================================================================
# ROUTER REGISTRATION
# =============================================================================

AdminRouter.include_routers(
    AdminPanelRouter,
    AdminRatesRouter,
    AdminHostsRouter,
    AdminNetworkRouter,
)

# =============================================================================
# USAGE EXAMPLE
# =============================================================================

"""
How to use in main.py:
---------------------
from handlers.admin.admin_router import AdminRouter

dp.include_router(AdminRouter)

All admin functionality is now available under the AdminRouter.
Each sub-router handles its own callbacks and states.

Available admin sections:
-------------------------
- /panel - Admin panel entry point
- Rates Management - Create, edit, delete tariffs
- Hosts Management - Create, edit, delete 3x-ui servers
"""