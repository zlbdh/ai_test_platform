# -*- coding: utf-8 -*-
"""
Routers Package - API routing modules
"""
from .core import router as core_router, setup_core_routes
from .testing import router as testing_router
from .knowledge import router as knowledge_router
from .graphql import router as graphql_router
from .websocket_test import router as ws_test_router
from .grpc import router as grpc_router
from .database import router as database_router
from .cicd import router as cicd_router
from .ai_enhancement import router as ai_enhancement_router
from .auth import router as auth_router
from .requirement import router as requirement_router
from .platform import router as platform_router, setup_platform_routes
from .advanced_testing import router as advanced_testing_router
from .oauth import router as oauth_router
from .plan import router as plan_router
from .history import router as history_router
from .data import router as data_router
from .report import router as report_router
from .commander import router as commander_router
from .deploy import router as deploy_router
from .exploration import router as exploration_router
from .release import router as release_router

__all__ = [
    "core_router", "setup_core_routes",
    "testing_router",
    "knowledge_router",
    "graphql_router",
    "ws_test_router",
    "grpc_router",
    "database_router",
    "cicd_router",
    "ai_enhancement_router",
    "auth_router",
    "requirement_router",
    "platform_router", "setup_platform_routes",
    "advanced_testing_router",
    "oauth_router",
    "plan_router",
    "history_router",
    "data_router",
    "report_router",
    "commander_router",
    "deploy_router",
    "exploration_router",
    "release_router",
]
