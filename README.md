# UP MSA Pro 2024 - Project 3 - Stage 2

### UPD 18.06
Зашел проверить работу картинок - сервер ОКН стал отдавать 403 на прокси запросы. Добавление заголовка user-agent в запрос решило проблему.

### Состав команды
 - Чибисов Михаил
 - Бабурина Екатерина
 - Маркевич Екатерина
 - Маренин Евгений

### Ссылка на карту
- https://estronnom.github.io/folium-kirov-okn/

### Quick start
```shell
pip install -r requirements.txt
python3 -m src.generate_folium_map
```

### Краткая информация о городе
**Киров**, город в России, административный центр Кировской области Нас. 475,8 тыс. чел. (2024). Расположен в центральной части области, на реке Вятка (вытянут вдоль берегов более чем на 25 км). Крупный транспортный узел. Речной порт. Аэропорт. 
Исторический, культурный, промышленный и научный центр Приуралья. Родина дымковской игрушки. Город трудовой доблести.

### Описание используемых данных с указанием источников
- Предоставленный с заданием csv-файл с информацией об ОКН Кировской области
- Выгруженный с помощью overpass turbo файл с границами города Киров (kirov_borders.geojson)

Note: в рамках генерации карты данные берутся напрямую из исходного .csv файла. Файл `export.geojson` размещен здесь по условию задания и для дальнейшей возможности быстрого переиспользования и валидации данных. 

### Описание основных методов
Логика скрипта разделена на несколько файлов, расположенных в папке `./src`:

- `data_parser.py`: набор инструкций для чтения и преобразования исходного csv датасета в рабочий формат. Здесь также расположены функции для чтения дополнительных файлов-ресурсов (вроде иконки маркера, границ датасета). Инстанс класса DataParser затем используется другими модулями для удобного доступа к данным.
- `config.py`: конфиг-файл с путями до всех нужных для генерации карты данных. При желании значения можно изменить и запустить работу скрипта для другого датасета.
- `map_maker.py`: содержит класс MapMaker, используемый для создания инстанса карты и дальнейшей его конфигурации.
- `html_popup.py`: файл с html-темплейтом попапа и функциями для его форматирования.
- `generate_folium_map.py`: entrypoint приложения
- `cors_proxy.py`: отдельный модуль, никак не связанный с остальной логикой приложения. Это микро-бекенд, который запускается на сервере и представляет собой прокси для обращения к картинкам с сайта okn-mk.mkrf.ru.

### Что было самым сложным в работе

Самым интересным было сделать html-попап для объектов с возможностью отображения картинок. Ссылки на медиа были в датасете, однако сервер минкульта не отдавал нужные cors заголовки, поэтому просто добавить ссылки в html не получилось. Понадобилось изобрести простенький прокси-бек, для обращения к все тем же картинкам. Далее надо было настроить кеш картинок на уровне nginx, так как большинство медиа были тяжеловесными и грузились достаточно долго.

В итоге получилось! Но не на 100% идеально, так как по некоторым ссылкам минкульт кажется отдает не картинки, а пдф-ки. В целом добавить их отображение не очень сложно, но мы не успели это доделать.

### Что получилось в работе и вы можете этим гордиться

См. выше историю с картинками.

В остальном практически все пункты задания получились без проблем.

### Что не получилось и почему

Поправить баг отображения состояния включенной подложки - при загрузке страницы рендерится верная опция, однако в LayerControl все подложки отображаются выключенными. Скорее всего какая-то особенность лифлета, не успел разобраться.

Сделать скрипт полностью датасет-независимым, добавить более тонкие опции конфигурации (например через CLI). Тут опять же не хватило времени.
