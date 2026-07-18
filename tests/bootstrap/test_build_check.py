from pathlib import Path

from bootstrap.build_check import missing_binaries, read_liboqs_commit


def test_missing_binaries_reports_targets_without_a_binary(tmp_path):
    (tmp_path / "kyber512_leak1").mkdir()
    (tmp_path / "kyber512_leak1" / "harness_oracle").write_text("fake binary")
    (tmp_path / "kyber512_leak2").mkdir()
    # leak2 has no binary

    missing = missing_binaries(tmp_path, target_dirs=("kyber512_leak1", "kyber512_leak2"))

    assert missing == ["kyber512_leak2"]


def test_missing_binaries_empty_when_all_present(tmp_path):
    for name in ("kyber512_leak1", "kyber512_leak2"):
        d = tmp_path / name
        d.mkdir()
        (d / "harness_oracle").write_text("fake binary")

    assert missing_binaries(tmp_path, target_dirs=("kyber512_leak1", "kyber512_leak2")) == []


def test_read_liboqs_commit_returns_file_contents(tmp_path):
    commit_file = tmp_path / "liboqs-commit.txt"
    commit_file.write_text("abc1234\n")

    assert read_liboqs_commit(commit_file) == "abc1234"


def test_read_liboqs_commit_returns_placeholder_when_missing(tmp_path):
    commit_file = tmp_path / "does-not-exist.txt"

    result = read_liboqs_commit(commit_file)

    assert "unknown" in result
