from pathlib import Path


class RasterReader:
    def read(self, file_path: str):
        return {"file_path": file_path, "status": "read"}
