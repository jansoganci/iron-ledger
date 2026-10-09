"""Storage adapter: missing files become a domain error; listing and bulk delete."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from storage3.utils import StorageException

from backend.adapters.supabase_storage import SupabaseFileStorage
from backend.domain.errors import StoredFileMissing

FOLDER = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b/2026-03-01"


def _storage():
    client = MagicMock()
    bucket = client.storage.from_.return_value
    return SupabaseFileStorage(client), bucket


@pytest.mark.parametrize(
    "payload",
    [
        {"statusCode": "404", "error": "not_found", "message": "Object not found"},
        {"statusCode": 400, "error": "not_found"},
        {"statusCode": 404},
    ],
)
def test_missing_object_raises_stored_file_missing(payload) -> None:
    storage, bucket = _storage()
    bucket.download.side_effect = StorageException(payload)
    with pytest.raises(StoredFileMissing):
        storage.download(f"{FOLDER}/gl.xlsx")


def test_other_storage_errors_are_not_reported_as_expired() -> None:
    storage, bucket = _storage()
    bucket.download.side_effect = StorageException({"statusCode": 403})
    with pytest.raises(StorageException):
        storage.download(f"{FOLDER}/gl.xlsx")


def test_list_folder_pages_and_skips_sub_folders() -> None:
    storage, bucket = _storage()
    first = [{"id": f"id-{i}", "name": f"f{i}.xlsx"} for i in range(100)]
    second = [{"id": "id-x", "name": "last.csv"}, {"id": None, "name": "nested"}]
    bucket.list.side_effect = [first, second]

    keys = storage.list_folder(FOLDER + "/")

    assert len(keys) == 101
    assert keys[0] == f"{FOLDER}/f0.xlsx" and keys[-1] == f"{FOLDER}/last.csv"
    assert bucket.list.call_args_list[1].args == (
        FOLDER,
        {"limit": 100, "offset": 100},
    )


@pytest.mark.parametrize("folder", ["", "/", "//"])
def test_list_folder_refuses_the_bucket_root(folder) -> None:
    storage, bucket = _storage()
    with pytest.raises(ValueError):
        storage.list_folder(folder)
    bucket.list.assert_not_called()


def test_delete_many_removes_in_chunks() -> None:
    storage, bucket = _storage()
    keys = [f"{FOLDER}/f{i}.xlsx" for i in range(150)]

    storage.delete_many(keys)

    chunks = [c.args[0] for c in bucket.remove.call_args_list]
    assert [len(c) for c in chunks] == [100, 50]
    assert sum(chunks, []) == keys
