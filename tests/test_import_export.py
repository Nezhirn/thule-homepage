"""Full-data export and transactional import invariants."""
from helpers import create_card, upload_image

CARD_FIELDS = ("title", "url", "icon_path", "size", "grid_col", "grid_row", "open_in_new_tab")
SETTINGS_FIELDS = ("background_image", "blur_radius", "dark_mode")


def export_payload(client):
    data = client.get("/api/full-data").json()
    cards = [{key: card.get(key) for key in CARD_FIELDS} for card in data["cards"]]
    settings = {key: data["settings"].get(key) for key in SETTINGS_FIELDS}
    return {"settings": settings, "cards": cards}


def test_full_data_returns_cards_in_grid_order(client):
    create_card(client, title="b", grid_col=2, grid_row=1)
    create_card(client, title="a", grid_col=1, grid_row=1)
    create_card(client, title="c", grid_col=1, grid_row=2)
    titles = [card["title"] for card in client.get("/api/full-data").json()["cards"]]
    assert titles == ["a", "b", "c"]


def test_import_replaces_all_cards(client):
    create_card(client, title="old")
    payload = {"cards": [{"title": "new", "grid_col": 1, "grid_row": 1}]}

    response = client.post("/api/import", json=payload)

    assert response.status_code == 200
    titles = [card["title"] for card in client.get("/api/cards").json()]
    assert titles == ["new"]


def test_import_rollback_keeps_cards_and_files_on_invalid_input(client, data_paths):
    filename = upload_image(client).json()["filename"]
    create_card(client, title="old", icon_path=filename)
    payload = {
        "cards": [
            {"title": "good", "url": "https://example.com"},
            {"title": "bad", "url": "javascript:alert(1)"},
        ]
    }

    response = client.post("/api/import", json=payload)

    assert response.status_code == 400
    cards = client.get("/api/cards").json()
    assert [card["title"] for card in cards] == ["old"]
    assert cards[0]["icon_path"] == filename
    assert (data_paths["uploads"] / filename).exists()


def test_import_export_roundtrip_preserves_icons(client, data_paths):
    filename = upload_image(client).json()["filename"]
    create_card(client, title="with icon", icon_path=filename)
    payload = export_payload(client)

    response = client.post("/api/import", json=payload)

    assert response.status_code == 200
    cards = client.get("/api/cards").json()
    assert cards[0]["icon_path"] == filename
    assert (data_paths["uploads"] / filename).exists()


def test_import_without_settings_keeps_background(client, data_paths):
    background = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": background})
    icon = upload_image(client).json()["filename"]
    create_card(client, title="card", icon_path=icon)

    response = client.post("/api/import", json=export_payload(client))

    assert response.status_code == 200
    settings = client.get("/api/settings").json()
    assert settings["background_image"] == background
    assert (data_paths["uploads"] / background).exists()


def test_import_explicit_null_clears_background(client, data_paths):
    background = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": background})

    response = client.post("/api/import", json={"settings": {"background_image": None}, "cards": []})

    assert response.status_code == 200
    assert client.get("/api/settings").json()["background_image"] is None
    assert not (data_paths["uploads"] / background).exists()


def test_import_replaces_background_and_deletes_old_file(client, data_paths):
    old = upload_image(client).json()["filename"]
    new = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": old})

    client.post("/api/import", json={"settings": {"background_image": new}, "cards": []})

    assert not (data_paths["uploads"] / old).exists()
    assert (data_paths["uploads"] / new).exists()


def test_import_preserves_open_mode(client):
    payload = {"cards": [{"title": "same tab", "open_in_new_tab": False}]}
    client.post("/api/import", json=payload)
    assert client.get("/api/cards").json()[0]["open_in_new_tab"] is False


def test_import_removes_orphaned_icons_after_commit(client, data_paths):
    filename = upload_image(client).json()["filename"]
    create_card(client, title="old", icon_path=filename)

    client.post("/api/import", json={"cards": [{"title": "new"}]})

    assert not (data_paths["uploads"] / filename).exists()


def test_import_keeps_file_reused_as_icon(client, data_paths):
    """A replaced background file must survive if a new card uses it as an icon."""
    filename = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": filename})

    payload = {
        "settings": {"background_image": None},
        "cards": [{"title": "icon user", "icon_path": filename}],
    }
    response = client.post("/api/import", json=payload)

    assert response.status_code == 200
    assert (data_paths["uploads"] / filename).exists()
    assert client.get("/api/cards").json()[0]["icon_path"] == filename


def test_clearing_background_keeps_file_used_as_icon(client, data_paths):
    filename = upload_image(client).json()["filename"]
    client.put("/api/settings", json={"background_image": filename})
    create_card(client, title="icon user", icon_path=filename)

    response = client.put("/api/settings", json={"background_image": None})

    assert response.status_code == 200
    assert (data_paths["uploads"] / filename).exists()


def test_import_rejects_too_many_cards(client):
    payload = {"cards": [{"title": "x"} for _ in range(1001)]}
    assert client.post("/api/import", json=payload).status_code == 422
