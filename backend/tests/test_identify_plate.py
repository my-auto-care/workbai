"""Check-in's plate scan: /vehicle/identify-plate (Chad, 2026-10-22: "a license plate scan tied to the vehicle database api")."""

import io

import pytest
from fastapi import HTTPException

import app.api.vehicle_lookup as lookup


@pytest.fixture
def providers(monkeypatch):
    calls = {"ocr": [], "plate_to_vin": [], "decode": []}

    async def ocr(data, filename, region="us"):
        calls["ocr"].append(region)
        return {"plate": "abc-1234", "confidence": 0.93, "region": region}

    async def plate_to_vin(plate, state):
        calls["plate_to_vin"].append((plate, state))
        return "5tdjzrfh1hs123456" if plate == "ABC1234" else None

    async def decode(vin):
        calls["decode"].append(vin)
        return {"year": 2017, "make": "Toyota", "model": "Highlander", "trim": "XLE", "engine_description": "3.5L V6", "source": "vehicledatabases_advanced"}

    monkeypatch.setattr(lookup, "VDB_KEY", "test-key")
    monkeypatch.setattr(lookup, "_ocr_plate", ocr)
    monkeypatch.setattr(lookup, "_vdb_plate_to_vin", plate_to_vin)
    monkeypatch.setattr(lookup, "_vdb_decode_vin", decode)
    return calls


def test_a_photo_becomes_a_vehicle_with_one_decode_and_no_paid_extras(client, world, bearer, providers, monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("check-in must not call recalls, maintenance, repairs or warranty")
    for name in ("_vdb_recalls", "_vdb_maintenance", "_vdb_repairs", "_vdb_warranty"):
        monkeypatch.setattr(lookup, name, boom)
    response = client.post("/vehicle/identify-plate", headers=bearer(world.advisor_a),
                           data={"state": "sc"}, files={"image": ("plate.jpg", io.BytesIO(b"\xff\xd8jpeg"), "image/jpeg")})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"plate": "ABC1234", "state": "SC", "confidence": 0.93, "vin": "5TDJZRFH1HS123456", "year": 2017, "make": "Toyota",
                    "model": "Highlander", "trim": "XLE", "engine": "3.5L V6", "source": "vehicledatabases_advanced"}
    assert providers["ocr"] == ["us-sc"], "the plate reader is told the state"
    assert providers["plate_to_vin"] == [("ABC1234", "SC")]
    assert len(providers["decode"]) == 1


def test_a_typed_plate_skips_the_photo_reader(client, world, bearer, providers):
    response = client.post("/vehicle/identify-plate", headers=bearer(world.tech_a1), data={"state": "SC", "plate": " abc 1234 "})
    assert response.status_code == 200, response.text
    assert response.json()["vin"] == "5TDJZRFH1HS123456"
    assert providers["ocr"] == []


def test_a_plate_the_database_does_not_know_says_so(client, world, bearer, providers):
    response = client.post("/vehicle/identify-plate", headers=bearer(world.admin_a), data={"state": "NC", "plate": "ZZZ999"})
    assert response.status_code == 200
    body = response.json()
    assert body["vin"] is None and body["plate"] == "ZZZ999" and "Enter the vehicle by hand" in body["message"]
    assert providers["decode"] == []


@pytest.mark.parametrize("data,status", [
    ({"state": "XX", "plate": "ABC1234"}, 422),
    ({"state": "SC", "plate": "!"}, 422),
    ({"state": "SC", "plate": "ABCDEFGHIJ"}, 422),
    ({"state": "SC"}, 422),
])
def test_bad_input_is_refused_before_any_provider_call(client, world, bearer, providers, data, status):
    response = client.post("/vehicle/identify-plate", headers=bearer(world.advisor_a), data=data)
    assert response.status_code == status, response.text
    assert providers["plate_to_vin"] == [] and providers["ocr"] == []


def test_a_non_image_and_an_oversized_photo_are_refused(client, world, bearer, providers, monkeypatch):
    response = client.post("/vehicle/identify-plate", headers=bearer(world.advisor_a), data={"state": "SC"},
                           files={"image": ("notes.txt", io.BytesIO(b"hello"), "text/plain")})
    assert response.status_code == 415
    monkeypatch.setattr(lookup, "MAX_PLATE_IMAGE_BYTES", 10)
    response = client.post("/vehicle/identify-plate", headers=bearer(world.advisor_a), data={"state": "SC"},
                           files={"image": ("plate.jpg", io.BytesIO(b"x" * 11), "image/jpeg")})
    assert response.status_code == 413
    assert providers["ocr"] == []


def test_provider_failures_never_leak_their_text(client, world, bearer, providers, monkeypatch):
    async def down(*args, **kwargs):
        raise HTTPException(status_code=502, detail="PlateRecognizer error: secret internal detail")
    monkeypatch.setattr(lookup, "_ocr_plate", down)
    response = client.post("/vehicle/identify-plate", headers=bearer(world.advisor_a), data={"state": "SC"},
                           files={"image": ("plate.jpg", io.BytesIO(b"\xff\xd8"), "image/jpeg")})
    assert response.status_code == 502
    assert "secret" not in response.text and "PlateRecognizer" not in response.text


def test_signed_out_and_the_voice_agent_are_refused(client, world, agent_headers, providers):
    assert client.post("/vehicle/identify-plate", data={"state": "SC", "plate": "ABC1234"}).status_code == 401
    assert client.post("/vehicle/identify-plate", headers=agent_headers, data={"state": "SC", "plate": "ABC1234"}).status_code == 401
    assert providers["plate_to_vin"] == []
