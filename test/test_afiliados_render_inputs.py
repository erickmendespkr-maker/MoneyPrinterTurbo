"""Regression tests for bounded, untrusted render-input packages."""
import io
import json
import zipfile

import pytest

from app.afiliados.render_inputs import pack_inputs, unpack_inputs


def _rewrite_zip(entries, *, compression=zipfile.ZIP_STORED):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=compression) as zip_file:
        for name, data in entries:
            zip_file.writestr(name, data)
    return memory.getvalue()


def test_roundtrip_preserves_approved_copy_and_media_only():
    raw = pack_inputs([b"photo-1", b"photo-2"], "Produto", 15, "Roteiro autorizado",
                      audio=b"ID3 audio", audio_extension=".mp3")
    payload = unpack_inputs(raw)
    assert payload.product_name == "Produto"
    assert payload.duration == 15
    assert payload.script == "Roteiro autorizado"
    assert payload.images == [b"photo-1", b"photo-2"]
    assert payload.audio == b"ID3 audio"
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert "owner_id" not in archive.read("manifest.json").decode("utf-8")
        assert "watermark" not in archive.read("manifest.json").decode("utf-8")
        assert "plan" not in archive.read("manifest.json").decode("utf-8")


def test_unauthenticated_user_cannot_inject_plan_watermark_or_owner():
    original = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    with zipfile.ZipFile(io.BytesIO(original)) as zip_file:
        entries = [(item.filename, zip_file.read(item.filename))
                   for item in zip_file.infolist()]
    manifest = json.loads(entries[0][1])
    manifest["plan"] = "creator"
    entries[0] = ("manifest.json", json.dumps(manifest).encode("utf-8"))
    with pytest.raises(ValueError, match="Manifesto"):
        unpack_inputs(_rewrite_zip(entries))


@pytest.mark.parametrize("invalid", [
    [], [b""], [b"x" * (12 * 1024 * 1024 + 1)],
])
def test_bad_photo_lists_fail_before_upload(invalid):
    with pytest.raises(ValueError):
        pack_inputs(invalid, "Produto", 15, "Roteiro")


@pytest.mark.parametrize("duration,script", [(17, "Roteiro"), (15, ""), (True, "Roteiro")])
def test_bad_script_or_duration_rejected(duration, script):
    with pytest.raises(ValueError):
        pack_inputs([b"photo"], "Produto", duration, script)


def test_archive_with_unexpected_file_or_path_traversal_rejected():
    raw = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [(i.filename, archive.read(i.filename)) for i in archive.infolist()]
    with pytest.raises(ValueError):
        unpack_inputs(_rewrite_zip(entries + [("../escape.txt", b"evil")]))


def test_duplicate_zip_members_rejected():
    raw = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [(i.filename, archive.read(i.filename)) for i in archive.infolist()]
    with pytest.raises(ValueError):
        unpack_inputs(_rewrite_zip(entries + [("photos/0.bin", b"overwrite")]))


def test_compressed_zip_bomb_is_rejected_without_decompression():
    raw = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [(i.filename, archive.read(i.filename)) for i in archive.infolist()]
    compressed = _rewrite_zip(entries, compression=zipfile.ZIP_DEFLATED)
    with pytest.raises(ValueError, match="Arquivos"):
        unpack_inputs(compressed)


def test_invalid_zip_and_corrupt_json_are_rejected():
    with pytest.raises(ValueError):
        unpack_inputs(b"not-a-zip")
    with pytest.raises(ValueError):
        unpack_inputs(_rewrite_zip([
            ("manifest.json", b"not-json"), ("photos/0.bin", b"p"),
        ]))


def test_extra_audio_and_missing_photo_are_rejected():
    raw = pack_inputs([b"photo"], "Produto", 15, "Roteiro")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = [(i.filename, archive.read(i.filename)) for i in archive.infolist()]
    with pytest.raises(ValueError):
        unpack_inputs(_rewrite_zip(entries + [("audio.bin", b"extra")]))
    with pytest.raises(ValueError):
        unpack_inputs(_rewrite_zip([entries[0]]))
