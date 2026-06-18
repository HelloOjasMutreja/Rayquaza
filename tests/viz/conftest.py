from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.fixture
def loop_state_leak5():
    return FIXTURES / "loop_state_leak5.json"

@pytest.fixture
def loop_state_leak2():
    return FIXTURES / "loop_state_leak2.json"

@pytest.fixture
def timing_leak5():
    return FIXTURES / "timing_leak5.json"

@pytest.fixture
def stdout_transcript():
    return (FIXTURES / "stdout_transcript.txt").read_text()
