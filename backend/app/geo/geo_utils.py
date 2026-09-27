def validate_bounds(bounds):
    return isinstance(bounds, (list, tuple)) and len(bounds) == 4
