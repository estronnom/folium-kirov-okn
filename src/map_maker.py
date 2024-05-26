import folium
import geopandas as gpd
from folium.plugins import Fullscreen, MarkerCluster, MiniMap, MousePosition, Search
from shapely import Polygon

from src import html_popup
from src.data_parser import (
    DataParser,
    get_borders_multipolygon,
    get_dataset_borders,
    get_marker_svg,
)


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


class MapMaker:
    def __init__(self, dp: DataParser):
        self.dp = dp
        self.map: folium.Map | None = None
        self.base_layer: folium.TileLayer | None = None
        self.marker_cluster: folium.plugins.marker_cluster.MarkerCluster | None = None

    def set_base_layer(self):
        self.base_layer = folium.TileLayer(
            tiles="https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?language=ru",
            name="CartoDB Voyager",
            attr="CartoDB Voyager",
            control=True,
            show=True,
        )

    def init_map(self) -> None:
        self.map = folium.Map(
            location=[
                get_borders_multipolygon().centroid.y,
                get_borders_multipolygon().centroid.x,
            ],
            zoom_start=13,
            tiles=self.base_layer,
            prefer_canvas=True,
        )

    def add_borders(self) -> None:
        borders_group = folium.FeatureGroup(name="Административные границы")
        folium.GeoJson(
            get_dataset_borders(),
            name="Границы города Киров",
            style_function=style_border_polygon,
        ).add_to(borders_group)
        borders_group.add_to(self.map)

    def add_fishnet(self) -> None:
        fishnet = get_fishnet(self.dp.feature_collection["features"])
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
        ).add_to(self.map)

    def add_extra_overlays(self) -> None:
        folium.TileLayer(
            "openstreetmap", name="OpenStreetMap", control=True, show=False
        ).add_to(self.map)
        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            name="Google Satellite",
            attr="Google Satellite",
            show=False,
            control=True,
        ).add_to(self.map)

    def add_parsed_data(self) -> None:
        marker_cluster = MarkerCluster(
            name="ОКН (точки)", options={"disableClusteringAtZoom": 17}
        )
        polygon_group = folium.FeatureGroup(name="ОКН (полигоны)")

        for feat in self.dp.okn_features:
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
                    icon=folium.CustomIcon(
                        icon_image=get_marker_svg(), icon_size=(30, 30)
                    ),
                ).add_to(marker_cluster)

        marker_cluster.add_to(self.map)
        polygon_group.add_to(self.map)

        self.marker_cluster = marker_cluster

    def add_map_extra(self) -> None:
        MousePosition(
            separator=", ",
            empty_string="Двигайте курсор для отображения координат",
            position="bottomleft",
        ).add_to(self.map)

        Fullscreen(
            position="bottomright",
            title="Полноэкранный режим",
            title_cancel="Закрыть полноэкранный режим",
            force_separate_button=True,
        ).add_to(self.map)

        MiniMap(
            width=220,
            height=200,
            tile_layer=self.base_layer,
            position="bottomleft",
            zoom_level_offset=-5,
        ).add_to(self.map)

        if self.marker_cluster:
            Search(
                layer=self.marker_cluster, search_label="name", search_zoom=16
            ).add_to(self.map)

        folium.LayerControl().add_to(self.map)

    def dump_map_to_html(self, path: str) -> None:
        self.map.save(path)
