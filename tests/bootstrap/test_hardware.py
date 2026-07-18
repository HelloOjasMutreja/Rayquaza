import pytest

from bootstrap.hardware import (
    TIERS,
    detect_disk_gb,
    detect_ram_gb,
    recommend_tier,
    tier_by_name,
)


def test_recommend_tier_returns_original_when_resources_are_ample():
    tier = recommend_tier(ram_gb=32.0, disk_gb=100.0)
    assert tier is not None
    assert tier.name == "original"


def test_recommend_tier_returns_lightweight_when_original_does_not_fit():
    tier = recommend_tier(ram_gb=10.0, disk_gb=20.0)
    assert tier is not None
    assert tier.name == "lightweight"


def test_recommend_tier_returns_none_when_nothing_fits():
    tier = recommend_tier(ram_gb=2.0, disk_gb=1.0)
    assert tier is None


def test_recommend_tier_boundary_is_inclusive():
    tier = recommend_tier(ram_gb=16.0, disk_gb=12.0)
    assert tier is not None
    assert tier.name == "original"


def test_tier_by_name_returns_matching_tier():
    tier = tier_by_name("lightweight")
    assert tier.models == ("qwen2.5:3b", "phi3:mini")


def test_tier_by_name_raises_on_unknown_name():
    with pytest.raises(ValueError):
        tier_by_name("nonexistent")


def test_detect_ram_gb_returns_positive_number():
    assert detect_ram_gb() > 0


def test_detect_disk_gb_returns_positive_number():
    assert detect_disk_gb() > 0


def test_tiers_ordered_original_first():
    assert TIERS[0].name == "original"


def test_fits_disk_true_when_enough_space():
    from bootstrap.hardware import fits_disk
    tier = tier_by_name("lightweight")
    assert fits_disk(tier, disk_gb=10.0) is True


def test_fits_disk_false_when_not_enough_space():
    from bootstrap.hardware import fits_disk
    tier = tier_by_name("original")
    assert fits_disk(tier, disk_gb=5.0) is False


def test_is_apple_silicon_true_on_darwin_arm64():
    from unittest.mock import patch
    from bootstrap.hardware import is_apple_silicon
    with patch("bootstrap.hardware.platform.system", return_value="Darwin"), \
         patch("bootstrap.hardware.platform.machine", return_value="arm64"):
        assert is_apple_silicon() is True


def test_is_apple_silicon_false_on_linux():
    from unittest.mock import patch
    from bootstrap.hardware import is_apple_silicon
    with patch("bootstrap.hardware.platform.system", return_value="Linux"), \
         patch("bootstrap.hardware.platform.machine", return_value="x86_64"):
        assert is_apple_silicon() is False
