from src.data_parser import DataParser
from src.map_maker import MapMaker

DATASET_CSV_PATH = "./kirov_okn_new.csv"
GEOJSON_POINTS_EXPORT_PATH = "./export.geojson"
MAP_EXPORT_PATH = "./index.html"


def main() -> None:
    dp = DataParser()
    dp.install_okn_features_from_csv(DATASET_CSV_PATH)
    dp.dump_okn_features_to_geojson(GEOJSON_POINTS_EXPORT_PATH)

    mm = MapMaker(dp)
    mm.set_base_layer()
    mm.init_map()
    mm.add_borders()
    mm.add_fishnet()
    mm.add_extra_overlays()
    mm.add_parsed_data()
    mm.add_map_extra()
    mm.dump_map_to_html(MAP_EXPORT_PATH)


if __name__ == "__main__":
    main()
