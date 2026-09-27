def validate_file_size(size_bytes: int, max_mb: int = 50) -> bool:
    return size_bytes <= max_mb * 1024 * 1024
