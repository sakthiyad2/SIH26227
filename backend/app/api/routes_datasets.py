from fastapi import APIRouter

router = APIRouter()


DATASET_CATALOG = [
    {
        "id": "sentinel",
        "name": "Copernicus Sentinel-1 and Sentinel-2",
        "provider": "European Union / Copernicus",
        "kind": "Optical and SAR",
        "access": "Public under Copernicus data policy",
        "url": "https://dataspace.copernicus.eu/",
        "coverage": "Global",
    },
    {
        "id": "landsat",
        "name": "USGS Landsat Collection 2",
        "provider": "USGS / NASA",
        "kind": "Multispectral and thermal",
        "access": "Public domain / USGS open data terms",
        "url": "https://www.usgs.gov/landsat-missions/landsat-collection-2",
        "coverage": "Global",
    },
    {
        "id": "bhuvan",
        "name": "NRSC / ISRO Bhuvan Earth Observation",
        "provider": "National Remote Sensing Centre, ISRO",
        "kind": "Earth observation imagery",
        "access": "Public access subject to Bhuvan terms",
        "url": "https://bhuvan.nrsc.gov.in/",
        "coverage": "India",
    },
]


@router.get("/datasets/catalog")
def dataset_catalog() -> dict:
    return {
        "ok": True,
        "policy": "Only publicly accessible, appropriately licensed, or organiser-provided datasets may be ingested. No classified, operational, or service-generated data.",
        "datasets": DATASET_CATALOG,
    }