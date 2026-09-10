"""Card CRUD, grid placement, scheme validation and reorder invariants."""
from helpers import create_card, upload_image


def test_create_card_basic(client):
    card = create_card(client)
    assert card["id"] > 0
    assert card["title"] == "Example"
    assert card["position"] == 0
    assert (card["grid_col"], card["grid_row"]) == (1, 1)


def test_auto_place_moves_to_free_cell(client):
    create_card(client, grid_col=1, grid_row=1)
    second = create_card(client, title="Second", grid_col=1, grid_row=1)
    assert (second["grid_col"], second["grid_row"]) == (2, 1)


def test_auto_place_respects_card_size(client):
    create_card(client, title="Big", size="2x2", grid_col=1, grid_row=1)
    # (2,1) is covered by the 2x2 card at (1,1)
    second = create_card(client, title="Small", grid_col=2, grid_row=1)
    assert (second["grid_col"], second["grid_row"]) == (3, 1)


def test_auto_place_wraps_to_next_row_past_last_column(client):
    for col in range(1, 8):
        create_card(client, title=f"c{col}", grid_col=col, grid_row=1)
    eighth = create_card(client, title="wrap", grid_col=7, grid_row=1)
    assert (eighth["grid_col"], eighth["grid_row"]) == (1, 2)


def test_create_rejects_invalid_size(client):
    assert client.post("/api/cards", json={"title": "x", "size": "3x3"}).status_code == 422


def test_create_rejects_grid_col_out_of_range(client):
    assert client.post("/api/cards", json={"title": "x", "grid_col": 99}).status_code == 422


def test_create_rejects_dangerous_url_schemes(client):
    for url in ["javascript:alert(1)", "data:text/html,<script>1</script>", "vbscript:msgbox(1)"]:
        response = client.post("/api/cards", json={"title": "x", "url": url})
        assert response.status_code == 400, f"{url!r} should be rejected"


def test_create_rejects_control_character_obfuscated_scheme(client):
    response = client.post("/api/cards", json={"title": "x", "url": "java\tscript:alert(1)"})
    assert response.status_code == 400


def test_update_can_clear_url_and_icon(client, data_paths):
    filename = upload_image(client).json()["filename"]
    card = create_card(client, icon_path=filename)
    assert (data_paths["uploads"] / filename).exists()

    response = client.put(f"/api/cards/{card['id']}", json={"url": None, "icon_path": None})

    assert response.status_code == 200
    assert response.json()["url"] is None
    assert response.json()["icon_path"] is None
    assert not (data_paths["uploads"] / filename).exists()


def test_partial_update_preserves_size_and_icon(client, data_paths):
    """Regression for C6: editing a card must not reset its size or icon."""
    filename = upload_image(client).json()["filename"]
    card = create_card(client, title="Big", size="2x2", icon_path=filename)

    response = client.put(f"/api/cards/{card['id']}", json={"title": "Renamed"})

    body = response.json()
    assert body["title"] == "Renamed"
    assert body["size"] == "2x2"
    assert body["icon_path"] == filename
    assert (data_paths["uploads"] / filename).exists()


def test_replacing_icon_deletes_old_file(client, data_paths):
    old = upload_image(client).json()["filename"]
    new = upload_image(client).json()["filename"]
    card = create_card(client, icon_path=old)

    client.put(f"/api/cards/{card['id']}", json={"icon_path": new})

    assert not (data_paths["uploads"] / old).exists()
    assert (data_paths["uploads"] / new).exists()


def test_shared_icon_survives_until_last_reference(client, data_paths):
    shared = upload_image(client).json()["filename"]
    replacement = upload_image(client).json()["filename"]
    first = create_card(client, title="one", icon_path=shared)
    second = create_card(client, title="two", grid_col=2, icon_path=shared)

    client.put(f"/api/cards/{first['id']}", json={"icon_path": replacement})
    assert (data_paths["uploads"] / shared).exists()

    assert client.delete(f"/api/cards/{second['id']}").status_code == 204
    assert not (data_paths["uploads"] / shared).exists()


def test_delete_card_returns_204_and_removes_icon(client, data_paths):
    filename = upload_image(client).json()["filename"]
    card = create_card(client, icon_path=filename)

    assert client.delete(f"/api/cards/{card['id']}").status_code == 204
    assert not (data_paths["uploads"] / filename).exists()
    assert client.delete(f"/api/cards/{card['id']}").status_code == 404


def test_update_missing_card_is_404(client):
    assert client.put("/api/cards/999999", json={"title": "x"}).status_code == 404


def test_reorder_requires_complete_unique_set(client):
    first = create_card(client, title="one")
    second = create_card(client, title="two", grid_col=2)

    assert client.post("/api/cards/reorder", json={"card_ids": [first["id"]]}).status_code == 400
    assert client.post("/api/cards/reorder", json={"card_ids": [first["id"], first["id"]]}).status_code == 400
    assert client.post("/api/cards/reorder", json={"card_ids": []}).status_code == 422

    response = client.post("/api/cards/reorder", json={"card_ids": [second["id"], first["id"]]})
    assert response.status_code == 200

    cards = {card["id"]: card for card in client.get("/api/cards").json()}
    assert (cards[second["id"]]["grid_col"], cards[second["id"]]["grid_row"]) == (1, 1)
    assert (cards[first["id"]]["grid_col"], cards[first["id"]]["grid_row"]) == (2, 1)


def test_reorder_unknown_id_is_rejected(client):
    card = create_card(client)
    assert client.post("/api/cards/reorder", json={"card_ids": [card["id"], 424242]}).status_code == 400
