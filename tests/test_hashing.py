from zotero_core.hashing import file_sha256

EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_lowercase_by_default(tmp_path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    assert file_sha256(path) == EMPTY


def test_uppercase_on_request(tmp_path):
    # The connector writes uppercase digests into pdf-status.csv and compares
    # them byte-wise when resuming a batch. Flipping that default would
    # invalidate every recorded run.
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    assert file_sha256(path, uppercase=True) == EMPTY.upper()


def test_hashes_content_in_blocks(tmp_path):
    import hashlib

    path = tmp_path / "big.bin"
    payload = b"x" * (1024 * 1024 * 2 + 7)
    path.write_bytes(payload)
    assert file_sha256(path) == hashlib.sha256(payload).hexdigest()
