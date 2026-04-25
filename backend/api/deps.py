from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from backend.adapters.anthropic_llm import AnthropicLLMClient
from backend.adapters.resend_email import ResendEmailSender
from backend.adapters.supabase_repos import (
    SupabaseAccountsRepo,
    SupabaseAnomaliesRepo,
    SupabaseCompaniesRepo,
    SupabaseEntriesRepo,
    SupabaseReportsRepo,
    SupabaseRunsRepo,
)
from backend.adapters.supabase_storage import SupabaseFileStorage
from backend.settings import get_settings


@lru_cache
def _supabase_client() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def get_entries_repo() -> SupabaseEntriesRepo:
    return SupabaseEntriesRepo(_supabase_client())


def get_anomalies_repo() -> SupabaseAnomaliesRepo:
    return SupabaseAnomaliesRepo(_supabase_client())


def get_reports_repo() -> SupabaseReportsRepo:
    return SupabaseReportsRepo(_supabase_client())


def get_runs_repo() -> SupabaseRunsRepo:
    return SupabaseRunsRepo(_supabase_client())


def get_companies_repo() -> SupabaseCompaniesRepo:
    return SupabaseCompaniesRepo(_supabase_client())


def get_accounts_repo() -> SupabaseAccountsRepo:
    return SupabaseAccountsRepo(_supabase_client())


def get_file_storage() -> SupabaseFileStorage:
    return SupabaseFileStorage(_supabase_client())


def get_llm_client() -> AnthropicLLMClient:
    return AnthropicLLMClient(get_settings().anthropic_api_key)


def get_email_sender() -> ResendEmailSender:
    s = get_settings()
    return ResendEmailSender(s.resend_api_key, s.resend_from_email)
