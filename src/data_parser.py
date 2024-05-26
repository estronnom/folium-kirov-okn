import base64
import csv
import json
import logging
from dataclasses import asdict, dataclass
from functools import lru_cache

from shapely import MultiPoint, MultiPolygon, Point

from src import config

TCoord = list[float]
TPolygon = list[list[TCoord]]


@dataclass
class OknFeature:
    id: int
    latitude: float  # Y
    longitude: float  # X
    polygon_coordinates: TPolygon | None

    title: str
    verbose_address: str
    okn_category: str
    okn_type: str
    historical_date: str
    image_url: str | None


@lru_cache(maxsize=None)
def get_dataset_borders() -> dict:
    with open(config.TARGET_GEOJSON_BORDERS) as border_fh:
        borders = json.load(border_fh)

    return borders


@lru_cache(maxsize=None)
def get_borders_multipolygon() -> MultiPolygon:
    return MultiPolygon(get_dataset_borders()["features"][0]["geometry"]["coordinates"])


@lru_cache(maxsize=None)
def get_marker_svg() -> str:
    with open(config.MARKER_SVG_PATH, "r") as marker_fh:
        svg_bytes = marker_fh.read()

    return "data:image/svg+xml;base64," + base64.b64encode(
        svg_bytes.encode("utf-8")
    ).decode("utf-8")


def unmarshall_image_url(marshalled_url: str) -> str | None:
    input_split = marshalled_url.split('""""')
    if len(input_split) >= 4 and input_split[3].startswith("https://"):
        return input_split[3]


def get_convex_hull_from_marshalled_coordinates(
    marshalled_coordinates: str,
) -> TPolygon | None:
    if not marshalled_coordinates:
        return

    try:
        unmarshalled_coordinates = json.loads(
            marshalled_coordinates.replace('""""', '"')
        )[0]["coordinates"]
    except Exception as exc:
        logging.exception(
            f"Failed to parse marshalled coordinates, skipping...\nError: {exc}"
        )
        return

    # reverse coordinates
    # unmarshalled_coordinates = [pair[::-1] for pair in unmarshalled_coordinates]

    mul_point = MultiPoint(unmarshalled_coordinates)
    convex_hull = mul_point.convex_hull.exterior.coords
    return [list(tup_pair) for tup_pair in convex_hull]


def new_feature_collection() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [],
    }


def make_okn_feature_from_csv_row(row: dict) -> OknFeature:
    return OknFeature(
        id=int(row["V1"]),
        latitude=float(row["Y"]),
        longitude=float(row["X"]),
        polygon_coordinates=get_convex_hull_from_marshalled_coordinates(row["Items"]),
        title=row["Объект"],
        verbose_address=row["Полный адрес"],
        okn_category=row["Категория историко-культурного значения"],
        okn_type=row["Вид объекта"],
        historical_date=row["дата создания"],
        image_url=unmarshall_image_url(row["Изображение"]),
    )


def make_geojson_feature_from_okn_feature(feature: OknFeature) -> dict:
    return {
        "type": "Feature",
        "properties": asdict(feature),
        "geometry": {
            "type": "Point",
            "coordinates": [feature.longitude, feature.latitude],
        },
    }


def check_if_point_within_borders(point: Point, borders: MultiPolygon) -> bool:
    return borders.contains(point)


class DataParser:
    def __init__(self):
        self.okn_features: list[OknFeature] = []
        self.feature_collection = new_feature_collection()

    def install_okn_features_from_csv(self, csv_path: str) -> None:
        with open(csv_path) as fh:
            csv_reader = csv.DictReader(fh)
            for row in csv_reader:
                okn_feature = make_okn_feature_from_csv_row(row)  # type: ignore

                if not check_if_point_within_borders(
                    Point(okn_feature.longitude, okn_feature.latitude),
                    get_borders_multipolygon(),
                ):
                    continue

                self.okn_features.append(okn_feature)
                self.feature_collection["features"].append(
                    make_geojson_feature_from_okn_feature(okn_feature)
                )

    def dump_okn_features_to_geojson(self, geojson_path: str) -> None:
        with open(geojson_path, "w") as out_geojson_fh:
            json.dump(self.feature_collection, out_geojson_fh, ensure_ascii=False)
