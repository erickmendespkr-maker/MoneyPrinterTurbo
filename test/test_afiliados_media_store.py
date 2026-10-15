import io

import pytest
from PIL import Image

from app.afiliados.media_store import MediaStore


OWNER_A = "owner-test-0001"
OWNER_B = "owner-test-0002"


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(output, format="PNG")
    return output.getvalue()


def test_png_persists_and_is_isolated(tmp_path):
    path = tmp_path / "media.sqlite"
    store = MediaStore(path)
    data = png_bytes()
    media_id = store.save(OWNER_A, "thumbnail", data)
    assert len(MediaStore(path).list(OWNER_A)) == 1
    assert store.list(OWNER_B) == []
    assert store.load(OWNER_A, media_id) == ("thumbnail", data)
    with pytest.raises(ValueError):
        store.load(OWNER_B, media_id)
    assert not store.delete(OWNER_B, media_id)
    assert store.delete(OWNER_A, media_id)
    assert store.list(OWNER_A) == []


def test_minimal_mp4_header_is_accepted_only_as_container_check(tmp_path):
    store = MediaStore(tmp_path / "media.sqlite")
    data = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 12
    media_id = store.save(OWNER_A, "video", data)
    assert store.load(OWNER_A, media_id) == ("video", data)


@pytest.mark.parametrize("kind,data", [
    ("thumbnail", b"not a png"),
    ("video", b"not a video"),
    ("unknown", b"hello"),
    ("thumbnail", b""),
])
def test_invalid_media_rejected(tmp_path, kind, data):
    with pytest.raises(ValueError):
        MediaStore(tmp_path / "media.sqlite").save(OWNER_A, kind, data)
