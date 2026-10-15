from app.afiliados.showcase import public_demo_videos, public_plan_comparison


def test_public_plans_match_actual_entitlements():
    table = public_plan_comparison()
    assert table["Vídeos por anúncio"] == [1, 1, 3]
    assert table["Capas por anúncio"] == [0, 0, 9]
    assert table["Salvar projetos"] == ["Não", "Sim", "Sim"]


def test_public_demos_only_explicit_deployed_mp4(tmp_path):
    demo_dir = tmp_path / "assets" / "afiliados" / "demos"
    demo_dir.mkdir(parents=True)
    (demo_dir / "one.mp4").write_bytes(b"sample video")
    (demo_dir / "private.txt").write_text("not a video")
    (demo_dir / "empty.mp4").touch()
    assert [p.name for p in public_demo_videos(tmp_path)] == ["one.mp4"]
    assert public_demo_videos(tmp_path, limit=1)[0].name == "one.mp4"


def test_no_demos_by_default(tmp_path):
    assert public_demo_videos(tmp_path) == []
