import sys

sys.path.insert(0, "/workspace")
from slug import slugify  # noqa: E402


def test_simple():
    assert slugify("Hello World") == "hello-world"


def test_punctuation():
    assert slugify("Rust, Go & Python!") == "rust-go-python"
