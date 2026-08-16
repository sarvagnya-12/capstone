"""Step 11: product CRUD + image upload/storage, Step 34's image-serving
addition, and the ownership-scoping pattern used throughout the app."""

import io

from PIL import Image

from tests.conftest import register_and_login


def _make_image_bytes(size=(64, 64), color=(200, 100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _upload_product(client, headers, name="Test Sneaker"):
    files = {"image": ("test.jpg", _make_image_bytes(), "image/jpeg")}
    data = {"name": name, "description": "A test product", "category": "footwear"}
    return client.post("/api/v1/products", headers=headers, data=data, files=files)


def test_upload_product_happy_path(client, auth_headers):
    resp = _upload_product(client, auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Test Sneaker"
    assert body["original_image_path"]
    assert body["preprocessed_image_path"]


def test_upload_product_rejects_wrong_content_type(client, auth_headers):
    files = {"image": ("test.txt", b"not an image", "text/plain")}
    data = {"name": "Bad Upload", "description": "x", "category": "footwear"}
    resp = client.post("/api/v1/products", headers=auth_headers, data=data, files=files)
    assert resp.status_code == 422


def test_upload_product_rejects_oversized_file(client, auth_headers):
    # content-type/extension are checked before size (product_service._validate_image),
    # so this doesn't need to be a real decodable image -- just correctly
    # typed junk bytes over the 10MB limit.
    oversized = b"\xff" * (10 * 1024 * 1024 + 1)
    files = {"image": ("big.jpg", oversized, "image/jpeg")}
    data = {"name": "Too Big", "description": "x", "category": "footwear"}
    resp = client.post("/api/v1/products", headers=auth_headers, data=data, files=files)
    assert resp.status_code == 422


def test_list_products_scoped_to_owner(client, auth_headers):
    _upload_product(client, auth_headers, name="Mine")

    other_token = register_and_login(client, "otheruser@test.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    _upload_product(client, other_headers, name="Theirs")

    mine = client.get("/api/v1/products", headers=auth_headers).json()
    theirs = client.get("/api/v1/products", headers=other_headers).json()

    assert [p["name"] for p in mine] == ["Mine"]
    assert [p["name"] for p in theirs] == ["Theirs"]


def test_get_product_ownership_scoping(client, auth_headers):
    product_id = _upload_product(client, auth_headers).json()["id"]

    other_token = register_and_login(client, "notowner@test.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    own = client.get(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert own.status_code == 200

    not_owner = client.get(f"/api/v1/products/{product_id}", headers=other_headers)
    assert not_owner.status_code == 404


def test_product_image_endpoint_serves_real_bytes(client, auth_headers):
    product_id = _upload_product(client, auth_headers).json()["id"]

    resp = client.get(f"/api/v1/products/{product_id}/image?kind=original", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    img = Image.open(io.BytesIO(resp.content))
    img.verify()


def test_product_image_endpoint_ownership_scoping(client, auth_headers):
    product_id = _upload_product(client, auth_headers).json()["id"]

    other_token = register_and_login(client, "imagesnooper@test.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = client.get(f"/api/v1/products/{product_id}/image", headers=other_headers)
    assert resp.status_code == 404
