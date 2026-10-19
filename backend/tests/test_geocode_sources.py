"""Place search: the local part answers alone, Nominatim is cached, rate limited and skipped after a 429."""
import asyncio

import httpx
import pytest

from app.api import geocode
from app.models import Place
from config import TTLCache

ITEM = {"osm_type": "way", "osm_id": 7, "lat": "52.2", "lon": "21.0", "display_name": "Marszałkowska 1, Warszawa",
        "address": {"road": "Marszałkowska", "house_number": "1"}}


class Client:
    calls = 0
    status = 200

    def __init__(self, **kwargs):
        pass

    async def get(self, url, **kwargs):
        Client.calls += 1
        return httpx.Response(Client.status, request=httpx.Request("GET", url), json=[ITEM])


@pytest.fixture
def nominatim(monkeypatch):
    Client.calls, Client.status = 0, 200
    monkeypatch.setattr(geocode.httpx, "AsyncClient", Client)
    monkeypatch.setattr(geocode, "_clients", {})
    monkeypatch.setattr(geocode, "_cache", TTLCache(600))
    monkeypatch.setattr(geocode, "_next_slot", 0.0)
    monkeypatch.setattr(geocode, "_cooldown_until", 0.0)
    monkeypatch.setattr(geocode, "_local", lambda q, near: [
        Place(id="stop-1", label="Marszałkowska", sublabel="Przystanek", position=(52.2, 21.0))])
    return Client


def test_local_source_never_calls_nominatim(nominatim):
    found = asyncio.run(geocode.geocode("Marszałkowska", source="local"))
    assert [p.id for p in found] == ["stop-1"]
    assert nominatim.calls == 0


def test_nominatim_answers_are_cached(nominatim):
    first = asyncio.run(geocode.geocode("Marszałkowska 1", source="nominatim"))
    second = asyncio.run(geocode.geocode("marszałkowska   1", source="nominatim"))
    assert [p.label for p in first] == [p.label for p in second] == ["Marszałkowska 1"]
    assert nominatim.calls == 1


def test_an_address_puts_nominatim_first(nominatim):
    found = asyncio.run(geocode.geocode("Marszałkowska 1"))
    assert [p.id for p in found] == ["osm:way:7", "stop-1"]


def test_after_a_429_nominatim_rests_and_local_places_still_answer(nominatim):
    nominatim.status = 429
    assert [p.id for p in asyncio.run(geocode.geocode("Marszałkowska 1"))] == ["stop-1"]
    nominatim.status = 200
    asyncio.run(geocode.geocode("Marszałkowska 2"))
    assert nominatim.calls == 1  # cooling down: not called again


def test_requests_too_close_together_skip_nominatim(nominatim, monkeypatch):
    monkeypatch.setattr(geocode, "_next_slot", geocode.time.monotonic() + 5)
    with pytest.raises(geocode.HTTPException) as err:
        asyncio.run(geocode.geocode("Marszałkowska 3", source="nominatim"))
    assert err.value.status_code == 502
    assert nominatim.calls == 0
