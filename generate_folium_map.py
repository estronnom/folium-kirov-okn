import base64
import csv
import json
import logging
from dataclasses import asdict, dataclass
from functools import lru_cache

import folium
import geopandas as gpd
from folium.plugins import Fullscreen, MarkerCluster, MiniMap, MousePosition, Search
from shapely import MultiPoint, MultiPolygon, Point, Polygon

import html_popup

DATASET_CSV_PATH = "kirov_okn_new.csv"
TARGET_GEOJSON_BORDERS = "kirov_borders.geojson"
MARKER_SVG_PATH = "map_marker.svg"
GEOJSON_POINTS_EXPORT_PATH = "export.geojson"

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
    with open(TARGET_GEOJSON_BORDERS) as border_fh:
        borders = json.load(border_fh)

    return borders


@lru_cache(maxsize=None)
def get_borders_multipolygon() -> MultiPolygon:
    return MultiPolygon(get_dataset_borders()["features"][0]["geometry"]["coordinates"])


@lru_cache(maxsize=None)
def get_marker_svg() -> str:
    with open(MARKER_SVG_PATH, "r") as marker_fh:
        svg_bytes = marker_fh.read()

    return "data:image/svg+xml;base64," + base64.b64encode(
        svg_bytes.encode("utf-8")
    ).decode("utf-8")


def style_border_polygon(_) -> dict:
    return {
        "fillColor": "#61b5ff",
        "color": "#292929",
        "weight": 2,
        "fillOpacity": 0.05,
    }


def style_okn_polygon() -> dict:
    return {
        "fillColor": "#61b5ff",
        "color": "#292929",
        "weight": 0.5,
        "fillOpacity": 0.5,
    }


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


def check_if_point_within_borders(point: Point, borders: MultiPolygon) -> bool:
    return borders.contains(point)


def get_fishnet(features: dict) -> gpd.GeoDataFrame:
    g_data = gpd.GeoDataFrame.from_features(features)
    g_data = g_data.set_crs("EPSG:4326").to_crs("EPSG:3857")
    min_x, min_y, max_x, max_y = g_data.total_bounds

    # Increasing extent by 10% to include extreme points into fishnet
    x_range = max_x - min_x
    y_range = max_y - min_y
    min_x -= 0.1 * x_range
    max_x += 0.1 * x_range
    min_y -= 0.1 * y_range
    max_y += 0.1 * y_range

    square_size = 1000
    x, y = (min_x, min_y)
    geom_array = []

    while y <= max_y:
        while x <= max_x:
            geom = Polygon(
                [
                    (x, y),
                    (x, y + square_size),
                    (x + square_size, y + square_size),
                    (x + square_size, y),
                    (x, y),
                ]
            )
            geom_array.append(geom)
            x += square_size
        x = min_x
        y += square_size

    fishnet = gpd.GeoDataFrame(geom_array, columns=["geometry"]).set_crs("EPSG:3857")
    fishnet["id"] = fishnet.index
    merged = gpd.sjoin(g_data, fishnet, how="left", predicate="within")
    merged["n"] = 1
    dissolve = merged.dissolve(by="index_right", aggfunc="count")
    fishnet.loc[dissolve.index, "n"] = dissolve.n.values
    fishnet = fishnet.to_crs("EPSG:4326")
    return fishnet


def main() -> None:
    dp = DataParser()
    dp.install_okn_features_from_csv(DATASET_CSV_PATH)
    dp.dump_okn_features_to_geojson(GEOJSON_POINTS_EXPORT_PATH)

    geojson_borders = get_dataset_borders()
    multipolygon_borders = get_borders_multipolygon()

    voyager_base = folium.TileLayer(
        tiles="https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?language=ru",
        name="CartoDB Voyager",
        attr="CartoDB Voyager",
        control=True,
        show=True,
    )

    f_map = folium.Map(
        location=[multipolygon_borders.centroid.y, multipolygon_borders.centroid.x],
        zoom_start=13,
        tiles=voyager_base,
        prefer_canvas=True,
    )

    borders_group = folium.FeatureGroup(name="Административные границы")
    folium.GeoJson(
        geojson_borders,
        name="Границы города Киров",
        style_function=style_border_polygon,
    ).add_to(borders_group)
    borders_group.add_to(f_map)

    fishnet = get_fishnet(dp.feature_collection["features"])
    folium.Choropleth(
        geo_data=fishnet,
        data=fishnet,
        columns=["id", "n"],
        fill_color="YlOrRd",
        fill_opacity=0.6,
        key_on="id",
        nan_fill_opacity=0,
        line_color="#0000",
        legend_name="Количество ОКН в секторе",
        name="Концентрация ОКН",
    ).add_to(f_map)

    folium.TileLayer(
        "openstreetmap", name="OpenStreetMap", control=True, show=False
    ).add_to(f_map)
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        name="Google Satellite",
        attr="Google Satellite",
        show=False,
        control=True,
    ).add_to(f_map)

    marker_cluster = MarkerCluster(
        name="ОКН (точки)", options={"disableClusteringAtZoom": 17}
    )
    polygon_group = folium.FeatureGroup(name="ОКН (полигоны)")

    for feat in dp.okn_features:
        description = html_popup.format_description(
            verbose_address=feat.verbose_address,
            okn_category=feat.okn_category,
            okn_type=feat.okn_type,
            historical_date=feat.historical_date,
        )
        formatted_popup = html_popup.format_popup_html(
            title=feat.title, description=description, media_url=feat.image_url
        )
        iframe = folium.branca.element.IFrame(
            html=formatted_popup, width=500, height=450
        )
        popup = folium.Popup(html=iframe, lazy=True, max_width=650)

        if feat.polygon_coordinates:
            folium.Polygon(
                locations=feat.polygon_coordinates,
                popup=popup,
                tooltip=feat.title,
                **style_okn_polygon(),
            ).add_to(polygon_group)
        else:
            folium.Marker(
                location=[feat.latitude, feat.longitude],
                popup=popup,
                tooltip=feat.title,
                name=feat.title,
                icon=folium.CustomIcon(icon_image=get_marker_svg(), icon_size=(30, 30)),
            ).add_to(marker_cluster)

    marker_cluster.add_to(f_map)
    polygon_group.add_to(f_map)

    MousePosition(
        separator=", ",
        empty_string="Двигайте курсор для отображения координат",
        position="bottomleft",
    ).add_to(f_map)

    Fullscreen(
        position="bottomright",
        title="Полноэкранный режим",
        title_cancel="Закрыть полноэкранный режим",
        force_separate_button=True,
    ).add_to(f_map)

    MiniMap(
        width=220,
        height=200,
        tile_layer=voyager_base,
        position="bottomleft",
        zoom_level_offset=-5,
    ).add_to(f_map)

    Search(layer=marker_cluster, search_label="name", search_zoom=16).add_to(f_map)

    folium.LayerControl().add_to(f_map)
    f_map.save("index.html")


if __name__ == "__main__":
    main()
