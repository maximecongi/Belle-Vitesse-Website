from unittest.mock import MagicMock, patch
import pytest
import requests

from services.common.kdrive.client import KDriveClient, KDriveError


def test_client_init():
    client = KDriveClient(token="custom_token", drive_id="12345", base_url="https://api.example.com", timeout=15)
    assert client.token == "custom_token"
    assert client.drive_id == "12345"
    assert client.base_url == "https://api.example.com"
    assert client.timeout == 15


@patch("requests.Session.request")
def test_get_file_success(mock_request):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": "success", "data": {"id": 100, "name": "MonDossier"}}
    mock_request.return_value = mock_resp

    client = KDriveClient(token="test", drive_id="99")
    data = client.get_file(100)

    assert data["id"] == 100
    assert data["name"] == "MonDossier"
    mock_request.assert_called_once_with(
        "GET",
        "https://api.infomaniak.com/3/drive/99/files/100",
        headers={"Authorization": "Bearer test", "Accept": "application/json"},
        timeout=30
    )


@patch("requests.Session.request")
def test_list_files_pagination(mock_request):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": "success",
        "data": [{"id": 1, "name": "f1"}],
        "has_more": True,
        "cursor": "next_cursor_token"
    }
    mock_request.return_value = mock_resp

    client = KDriveClient(token="test", drive_id="99")
    items, cursor, has_more = client.list_files(48, cursor="prev", limit=50)

    assert len(items) == 1
    assert cursor == "next_cursor_token"
    assert has_more is True


@patch("requests.Session.request")
def test_create_directory_with_relative_path(mock_request):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": "success", "data": {"id": 200, "name": "BVPR-1234"}}
    mock_request.return_value = mock_resp

    client = KDriveClient(token="test", drive_id="99")
    res = client.create_directory(48, "BVPR-1234", relative_path="2026/09/PROD/PROJ")

    assert res["id"] == 200
    mock_request.assert_called_once_with(
        "POST",
        "https://api.infomaniak.com/3/drive/99/files/48/directory",
        headers={"Authorization": "Bearer test", "Accept": "application/json"},
        timeout=30,
        json={"name": "BVPR-1234", "relative_path": "2026/09/PROD/PROJ"}
    )


@patch("requests.Session.request")
def test_create_directory_already_exists_fallback(mock_request):
    # 1er appel: 400 destination_already_exists
    err_resp = MagicMock()
    err_resp.ok = False
    err_resp.status_code = 400
    err_resp.json.return_value = {
        "result": "error",
        "error": {"code": "destination_already_exists", "description": "Already exists"}
    }

    # 2eme appel: list_files sous parent 48
    list_resp = MagicMock()
    list_resp.ok = True
    list_resp.status_code = 200
    list_resp.json.return_value = {
        "result": "success",
        "data": [{"id": 300, "name": "EXISTING_FOLDER"}],
        "has_more": False
    }

    mock_request.side_effect = [err_resp, list_resp]

    client = KDriveClient(token="test", drive_id="99")
    res = client.create_directory(48, "EXISTING_FOLDER")

    assert res["id"] == 300
    assert res["name"] == "EXISTING_FOLDER"


@patch("requests.Session.request")
def test_upload_success(mock_request):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": "success", "data": {"id": 555, "name": "contrat.pdf", "size": 12}}
    mock_request.return_value = mock_resp

    client = KDriveClient(token="test", drive_id="99")
    res = client.upload(48, "contrat.pdf", b"hello content", conflict="error")

    assert res["id"] == 555
    mock_request.assert_called_once_with(
        "POST",
        "https://api.infomaniak.com/3/drive/99/upload",
        params={"total_size": 13, "directory_id": 48, "file_name": "contrat.pdf", "conflict": "error"},
        data=b"hello content",
        headers={"Authorization": "Bearer test", "Accept": "application/json", "Content-Type": "application/octet-stream"},
        timeout=30
    )


@patch("requests.Session.request")
def test_upload_duplicate_error_recovers_existing(mock_request):
    # 1er appel: 409 file_already_exists_error
    err_resp = MagicMock()
    err_resp.ok = False
    err_resp.status_code = 409
    err_resp.json.return_value = {
        "result": "error",
        "error": {"code": "file_already_exists_error", "description": "The file already exist"}
    }

    # 2eme appel: list_files pour retrouver l'ID
    list_resp = MagicMock()
    list_resp.ok = True
    list_resp.status_code = 200
    list_resp.json.return_value = {
        "result": "success",
        "data": [{"id": 777, "name": "photo.jpg"}],
        "has_more": False
    }

    mock_request.side_effect = [err_resp, list_resp]

    client = KDriveClient(token="test", drive_id="99")
    res = client.upload(48, "photo.jpg", b"fake image", conflict="error")

    assert res["id"] == 777


@patch("requests.Session.request")
def test_move_success(mock_request):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": "success", "data": {"cancel_id": "cancel-uuid-1", "valid_until": 1790035000}}
    mock_request.return_value = mock_resp

    client = KDriveClient(token="test", drive_id="99")
    res = client.move(100, 200)

    assert res["cancel_id"] == "cancel-uuid-1"
    mock_request.assert_called_once_with(
        "POST",
        "https://api.infomaniak.com/3/drive/99/files/100/move/200",
        headers={"Authorization": "Bearer test", "Accept": "application/json"},
        timeout=30,
        json={"conflict": "error"}
    )


@patch("requests.Session.request")
def test_delete_success(mock_request):
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": "success", "data": {"cancel_id": "del-uuid-1"}}
    mock_request.return_value = mock_resp

    client = KDriveClient(token="test", drive_id="99")
    res = client.delete(500)

    assert res["cancel_id"] == "del-uuid-1"
    mock_request.assert_called_once_with(
        "DELETE",
        "https://api.infomaniak.com/2/drive/99/files/500",
        headers={"Authorization": "Bearer test", "Accept": "application/json"},
        timeout=30
    )


@patch("requests.Session.request")
def test_delete_404_already_deleted(mock_request):
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"result": "error", "error": {"code": "not_found"}}
    mock_request.return_value = mock_resp

    client = KDriveClient(token="test", drive_id="99")
    res = client.delete(500)

    assert res.get("already_deleted") is True


@patch("time.sleep")
@patch("requests.Session.request")
def test_retry_on_500_error(mock_request, mock_sleep):
    err_resp = MagicMock()
    err_resp.ok = False
    err_resp.status_code = 500
    err_resp.json.return_value = {"result": "error", "error": {"code": "internal_server_error"}}

    ok_resp = MagicMock()
    ok_resp.ok = True
    ok_resp.status_code = 200
    ok_resp.json.return_value = {"result": "success", "data": {"id": 123}}

    mock_request.side_effect = [err_resp, ok_resp]

    client = KDriveClient(token="test", drive_id="99")
    res = client.get_file(123)

    assert res["id"] == 123
    assert mock_request.call_count == 2
    mock_sleep.assert_called_once_with(2)
