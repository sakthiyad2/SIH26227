import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

try:
    from backend.main import app
except ModuleNotFoundError:  # pragma: no cover - fallback for direct backend execution
    from main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_database(tmp_path, monkeypatch):
    database = __import__('app.db.database', fromlist=['database'])
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'satellite.db')
    database.init_db()

    ingestion_module = __import__('app.services.ingestion_service', fromlist=['IngestionService'])

    class NoOpVectorService:
        def add_vectors(self, vectors, tile_ids):
            pass

    monkeypatch.setattr(ingestion_module, 'VectorService', NoOpVectorService)


def test_health_endpoint():
    response = client.get('/api/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'


def test_metadata_and_ingestion(tmp_path):
    img_path = tmp_path / 'synthetic_scene.tif'
    img = Image.new('RGB', (32, 32), color=(10, 20, 30))
    img.save(img_path)

    service = __import__('app.services.ingestion_service', fromlist=['IngestionService']).IngestionService()
    result = service.ingest_path(str(img_path))
    assert result['status'] in {'indexed', 'duplicate'}


def test_duplicate_ingestion_repairs_missing_file_path(tmp_path):
    first_path = tmp_path / 'first.png'
    replacement_path = tmp_path / 'replacement.png'
    Image.new('RGB', (32, 32), color=(12, 24, 36)).save(first_path)
    Image.new('RGB', (32, 32), color=(12, 24, 36)).save(replacement_path)

    service = __import__('app.services.ingestion_service', fromlist=['IngestionService']).IngestionService()
    first_result = service.ingest_path(str(first_path))
    first_path.unlink()
    replacement_result = service.ingest_path(str(replacement_path))

    database = __import__('app.db.database', fromlist=['get_connection'])
    conn = database.get_connection()
    scene = conn.execute('SELECT file_path FROM scenes WHERE id = ?', (first_result['scene_id'],)).fetchone()
    tile = conn.execute('SELECT image_path FROM tiles WHERE scene_id = ?', (first_result['scene_id'],)).fetchone()
    conn.close()

    assert replacement_result['status'] == 'duplicate'
    assert replacement_result['scene_id'] == first_result['scene_id']
    assert scene['file_path'] == str(replacement_path.resolve())
    assert tile['image_path'] == str(replacement_path.resolve())


def test_semantic_search_excludes_fixtures_and_missing_images(tmp_path, monkeypatch):
    fixture_path = tmp_path / 'fixture.png'
    missing_path = tmp_path / 'missing.png'
    valid_path = tmp_path / 'valid.png'
    for index, image_path in enumerate((fixture_path, missing_path, valid_path)):
        Image.new('RGB', (32, 32), color=(20 + index, 40, 60)).save(image_path)
    fixture_path.with_suffix('.png.json').write_text(
        json.dumps({'source': 'synthetic-test-data', 'sensor': 'synthetic'}),
        encoding='utf-8',
    )

    ingestion = __import__('app.services.ingestion_service', fromlist=['IngestionService']).IngestionService()
    fixture = ingestion.ingest_path(str(fixture_path))
    missing = ingestion.ingest_path(str(missing_path))
    valid = ingestion.ingest_path(str(valid_path))
    missing_path.unlink()

    search_module = __import__('app.services.semantic_search_service', fromlist=['SemanticSearchService'])
    hits = [(fixture['tile_id'], 0.9), (missing['tile_id'], 0.8), (valid['tile_id'], 0.7)]

    class StubVectorService:
        def load_from_disk(self):
            pass

        def replace_vectors(self, vectors, tile_ids):
            pass

        def get_count(self):
            return len(hits)

        def search(self, query_vector, top_k=5):
            return hits[:top_k]

    monkeypatch.setattr(search_module, 'VectorService', StubVectorService)
    results = search_module.SemanticSearchService().search('river')

    assert [result['tile_id'] for result in results] == [valid['tile_id']]


def test_semantic_search_applies_metadata_and_aoi_filters(tmp_path, monkeypatch):
    records = [
        ('inside.png', 'Sentinel-2', '2025-06-15T10:00:00', '10%', '5,5'),
        ('outside.png', 'Landsat 8', '2024-06-15T10:00:00', 40, '20,20'),
    ]
    ingestion = __import__('app.services.ingestion_service', fromlist=['IngestionService']).IngestionService()
    tile_ids = {}
    for index, (filename, sensor, acquired, cloud_cover, centroid) in enumerate(records):
        image_path = tmp_path / filename
        Image.new('RGB', (32, 32), color=(30 + index, 50, 70)).save(image_path)
        image_path.with_suffix(image_path.suffix + '.json').write_text(
            json.dumps({
                'source': 'public-dataset',
                'sensor': sensor,
                'acquisition_datetime': acquired,
                'cloud_cover': cloud_cover,
                'centroid': centroid,
                'crs': 'EPSG:4326',
            }),
            encoding='utf-8',
        )
        tile_ids[filename] = ingestion.ingest_path(str(image_path))['tile_id']

    aoi_id = 'test-aoi'
    polygon = {
        'type': 'Polygon',
        'coordinates': [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
    }
    database = __import__('app.db.database', fromlist=['get_connection'])
    conn = database.get_connection()
    conn.execute(
        'INSERT INTO aoi (id, name, geometry, crs) VALUES (?, ?, ?, ?)',
        (aoi_id, 'Test area', json.dumps(polygon), 'EPSG:4326'),
    )
    conn.commit()
    conn.close()

    search_module = __import__('app.services.semantic_search_service', fromlist=['SemanticSearchService'])
    hits = [(tile_ids['inside.png'], 0.9), (tile_ids['outside.png'], 0.8)]

    class StubVectorService:
        def load_from_disk(self):
            pass

        def replace_vectors(self, vectors, tile_ids):
            pass

        def get_count(self):
            return len(hits)

        def search(self, query_vector, top_k=5):
            return hits[:top_k]

    monkeypatch.setattr(search_module, 'VectorService', StubVectorService)
    service = search_module.SemanticSearchService()
    assert [item['tile_id'] for item in service.search('river', {'sensor': 'Sentinel-2'})] == [tile_ids['inside.png']]
    assert [item['tile_id'] for item in service.search('river', {'date_from': '2025-01-01'})] == [tile_ids['inside.png']]
    assert [item['tile_id'] for item in service.search('river', {'max_cloud_cover': 0.2})] == [tile_ids['inside.png']]
    assert [item['tile_id'] for item in service.search('river', {'aoi': aoi_id})] == [tile_ids['inside.png']]

    options = client.get('/api/search/filters').json()
    assert options['sensors'] == ['Landsat 8', 'Sentinel-2']
    assert options['aois'] == [{'id': aoi_id, 'name': 'Test area'}]


def test_change_detection_pipeline(tmp_path):
    before = tmp_path / 'before.tif'
    after = tmp_path / 'after.tif'
    Image.new('RGB', (32, 32), (32, 32, 32)).save(before)
    Image.new('RGB', (32, 32), (80, 80, 80)).save(after)

    init_db = __import__('app.db.database', fromlist=['init_db']).init_db
    init_db()

    ingestion = __import__('app.services.ingestion_service', fromlist=['IngestionService']).IngestionService()
    before_result = ingestion.ingest_path(str(before))
    after_result = ingestion.ingest_path(str(after))

    service = __import__('app.services.change_detection_service', fromlist=['ChangeDetectionService']).ChangeDetectionService()
    payload = {'scene_a_id': before_result['scene_id'], 'scene_b_id': after_result['scene_id']}
    res = service.detect_change(payload)
    assert 'change_type' in res
    assert 0 <= res['confidence'] <= 1


def test_review_queue_and_decision_api():
    database = __import__('app.db.database', fromlist=['get_connection'])
    conn = database.get_connection()
    conn.execute('INSERT INTO change_detections (id) VALUES (?)', ('test-change',))
    conn.commit()
    conn.close()

    response = client.post('/api/review/test-change/confirm', json={
        'decision': 'confirm',
        'reason': 'valid anomaly',
        'reviewer': 'analyst',
    })
    assert response.status_code == 200
    body = response.json()
    assert body['decision']['decision'] == 'confirm'

    queue = client.get('/api/review/queue')
    assert queue.status_code == 200
    payload = queue.json()
    assert 'queue' in payload

    seen = set()
    for item in payload['queue']:
        key = item.get('id') or item.get('change_id')
        assert key not in seen
        seen.add(key)
