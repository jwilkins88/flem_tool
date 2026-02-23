# pylint: disable=abstract-method, missing-module-docstring
import json
import os
from typing import Callable
from threading import Timer, Thread

from loguru import logger
import requests
from flem.models.config import ModulePositionConfig
from flem.models.config_schema import ModuleSchema
from flem.models.modules.animator_config import AnimatorConfig, AnimatorConfigArguments
from flem.models.modules.weather_config import WeatherConfig, WeatherConfigSchema
from flem.modules.animator_module import AnimatorModule
from flem.modules.matrix_module import MatrixModule
from flem.utilities.utilities import parse_int


class WeatherModule(MatrixModule):
    __config: WeatherConfig = None
    __weather_file = f"{os.path.expanduser('~')}/.flem/weather_cache.json"
    __weather_timer: Timer = None
    __weather_update_interval = 600
    __animator_files_root = f"{os.path.expanduser('~')}/.flem/animator_files"
    __condition_mapping = {
        "Clouds": f"{__animator_files_root}/weather/cloudy.json",
        "Clear": f"{__animator_files_root}/weather/clear.json",
        "Rain": f"{__animator_files_root}/weather/cloud_rain.json",
        "Drizzle": f"{__animator_files_root}/weather/cloud_rain.json",
        "Thunderstorm": f"{__animator_files_root}/weather/cloud_storm.json",
        "Snow": f"{__animator_files_root}/weather/snowflake.json",
        "Mist": f"{__animator_files_root}/weather/fog.json",
        "Smoke": f"{__animator_files_root}/weather/fog.json",
        "Haze": f"{__animator_files_root}/weather/fog.json",
        "Dust": f"{__animator_files_root}/weather/fog.json",
        "Fog": f"{__animator_files_root}/weather/fog.json",
        "Sand": f"{__animator_files_root}/weather/fog.json",
        "Ash": f"{__animator_files_root}/weather/fog.json",
        "Squall": f"{__animator_files_root}/weather/fog.json",
        "Tornado": f"{__animator_files_root}/weather/fog.json",
    }
    __wind_directions = {
        "N": [[0, 1, 0], [0, 1, 0], [0, 0, 0]],
        "NE": [[0, 0, 1], [0, 1, 0], [0, 0, 0]],
        "E": [[0, 0, 0], [0, 1, 1], [0, 0, 0]],
        "SE": [[0, 0, 0], [0, 1, 0], [0, 0, 1]],
        "S": [[0, 0, 0], [0, 1, 0], [0, 1, 0]],
        "SW": [[0, 0, 0], [0, 1, 0], [1, 0, 0]],
        "W": [[0, 0, 0], [1, 1, 0], [0, 0, 0]],
        "NW": [[1, 0, 0], [0, 1, 0], [0, 0, 0]],
    }
    __icon_module: MatrixModule = None
    __icon_module_thread: Thread = None

    module_name = "Weather Module"

    def __init__(self, config: WeatherConfig, width: int = 9, height: int = 13):
        super().__init__(config, width, height)

        if not isinstance(config, WeatherConfig):
            self.__config = WeatherConfigSchema().load(ModuleSchema().dump(config))
        else:
            self.__config = config

        self.__get_weather_from_api()

    def start(
        self,
        update_device: Callable[[], None],
        write_queue: Callable[[tuple[int, int, bool]], None],
        execute_callback: bool = True,
        start_thread: bool = True,
    ):
        self.running = True
        self.reset()
        self.__weather_timer = Timer(
            self.__weather_update_interval, self.__get_weather_from_api
        )
        self.__weather_timer.name = "weather_update"
        if start_thread:
            self.__weather_timer.start()
        self.write(update_device, write_queue, execute_callback)

    def stop(self) -> None:
        self.running = False
        if self.__icon_module and self.__icon_module.running:
            self.__icon_module.stop()

        super().stop()

    def write(
        self,
        update_device: Callable[[], None],
        write_queue: Callable[[tuple[int, int, bool]], None],
        execute_callback: bool = True,
        refresh_override: int = None,
        running: bool = True,
    ) -> None:
        try:
            while self.running:
                if self.__weather_timer.finished.is_set():
                    logger.info("weather timer is finished")
                    self.__weather_timer = Timer(
                        self.__weather_update_interval, self.__get_weather_from_api
                    )
                    self.__weather_timer.name = "weather_update"
                    self.__weather_timer.start()

                weather = None
                if os.path.exists(self.__weather_file):
                    with open(self.__weather_file, "r", encoding="utf-8") as f:
                        weather = json.loads(f.read())

                weather_icon = weather

                for prop in self.__config.arguments.response_icon_property.split("."):
                    prop_as_int = parse_int(prop)

                    if prop_as_int is not None:
                        weather_icon = weather_icon[prop_as_int]
                        continue

                    weather_icon = weather_icon[prop]

                start_row = self.__config.position.y

                self.__draw_icon(
                    weather_icon,
                    start_row,
                    self.__config.position.x,
                    write_queue,
                    update_device,
                )

                del weather_icon

                start_row += 7

                self._write_array(
                    [[1, 1, 1, 1, 1, 1, 1, 1, 1]],
                    start_row,
                    self.__config.position.x,
                    write_queue,
                )
                start_row += 2

                self.__draw_temp(write_queue, weather, start_row)

                start_row += 6

                if self.__config.arguments.show_humidity:
                    self.__draw_humidity(write_queue, weather, start_row)
                    start_row += 8

                if self.__config.arguments.show_wind_speed:
                    self.__draw_wind_speed(write_queue, weather, start_row)
                    start_row += 8

                del weather
                super().write(
                    update_device,
                    write_queue,
                    execute_callback,
                    refresh_override,
                    self.running,
                )
        except (IndexError, ValueError, TypeError, KeyError) as e:
            logger.exception(f"Error while running {self.module_name}: {e}")
            super().stop()
            super().clear_module(update_device, write_queue)

    def __get_weather_from_api(self) -> None:
        try:
            weather_api_url = self.__config.arguments.api_url.format(
                api_key=self.__config.arguments.api_key,
                city_id=self.__config.arguments.city_id,
                temperature_unit=self.__config.arguments.temperature_unit,
            )
            logger.info(f"Getting weather from API: {weather_api_url}")
            response = requests.get(weather_api_url, timeout=5)
            weather = response.text
            logger.info(f"Got weather from API: {weather}")
            with open(self.__weather_file, "w", encoding="utf-8") as f:
                f.write(str(weather))
        except Exception as e:
            logger.exception(f"Error while getting weather from API: {e}")

    def __draw_temp(
        self,
        write_queue: Callable[[tuple[int, int, bool]], None],
        weather: dict,
        start_row: int,
    ) -> None:
        temperature = weather

        for prop in self.__config.arguments.response_temperature_property.split("."):
            temperature = temperature[prop]

        start_col = self.__config.position.x

        temperature = str(round(temperature))

        for char in temperature:
            if len(temperature) < 3:
                start_col += 2
                self._write_object(
                    char,
                    write_queue,
                    start_row,
                    start_col,
                )
                start_col += 1
                # self._write_object("degree", write_queue, start_row - 1, start_col - 1)
            else:
                self._write_object(
                    char,
                    write_queue,
                    start_row,
                    start_col,
                )
                if char == "-":
                    start_col += 2
                else:
                    start_col += 3

        del temperature

        # self._write_object("degree", write_queue, start_row - 1, start_col - 1)

    def __draw_wind_speed(
        self,
        write_queue: Callable[[tuple[int, int, bool]], None],
        weather: dict,
        start_row: int,
    ) -> None:
        wind_speed = weather
        wind_direction = weather

        self._write_array(
            [[1, 0, 1, 0, 1, 0, 1, 0, 1]],
            start_row,
            self.__config.position.x,
            write_queue,
        )
        start_row += 2

        for prop in self.__config.arguments.response_wind_speed_property.split("."):
            wind_speed = wind_speed[prop]

        wind_speed = str(round(wind_speed))

        for prop in self.__config.arguments.response_wind_direction_property.split("."):
            wind_direction = wind_direction[prop]

        start_col = self.__config.position.x

        if len(wind_speed) < 2:
            wind_speed = "0" + wind_speed

        for char in wind_speed:
            self._write_object(
                char,
                write_queue,
                start_row,
                start_col,
            )
            start_col += 3

        del wind_speed

        wind_direction = self.__determine_wind_direction(wind_direction)

        self._write_array(
            self.__wind_directions[wind_direction],
            start_row + 1,
            start_col,
            write_queue,
        )

        del wind_direction

    def __draw_humidity(
        self,
        write_queue: Callable[[tuple[int, int, bool]], None],
        weather: dict,
        start_row: int,
    ) -> None:
        humidity = weather

        self._write_array(
            [[1, 0, 1, 0, 1, 0, 1, 0, 1]],
            start_row,
            self.__config.position.x,
            write_queue,
        )

        start_row += 2

        for prop in self.__config.arguments.response_humidity_property.split("."):
            humidity = humidity[prop]

        humidity = str(round(humidity))

        if len(humidity) < 2:
            humidity = "0" + humidity

        start_col = self.__config.position.x

        for char in humidity:
            self._write_object(
                char,
                write_queue,
                start_row,
                start_col,
            )
            start_col += 4

        del humidity

    def __determine_wind_direction(self, wind_direction: int) -> str:
        wind_direction = round(wind_direction)
        cardinal_direction = None
        if 0 <= wind_direction < 15 or 345 <= wind_direction <= 360:
            cardinal_direction = "N"
        if 15 <= wind_direction < 75:
            cardinal_direction = "NE"
        if 75 <= wind_direction < 105:
            cardinal_direction = "E"
        if 105 <= wind_direction < 165:
            cardinal_direction = "SE"
        if 165 <= wind_direction < 195:
            cardinal_direction = "S"
        if 195 <= wind_direction < 255:
            cardinal_direction = "SW"
        if 255 <= wind_direction < 285:
            cardinal_direction = "W"
        if 285 <= wind_direction < 345:
            cardinal_direction = "NW"

        return cardinal_direction

    def __draw_icon(
        self,
        icon: str,
        start_row: int,
        start_col: int,
        write_queue: Callable[[tuple[int, int, bool]], None],
        update_device: Callable[[], None],
    ) -> None:
        if (
            self.__icon_module
            and self.__icon_module_thread.name
            == f"weather_{icon}_{id(self)}_{id(self.__icon_module)}"
            and self.__icon_module_thread.is_alive()
        ):
            return
        if self.__icon_module and self.__icon_module.running:
            self.__icon_module.stop()
            self.__icon_module_thread.join()
        logger.info(f"Drawing icon: {icon}")
        self.__icon_module = AnimatorModule(
            AnimatorConfig(
                position=ModulePositionConfig(x=start_col, y=start_row),
                arguments=AnimatorConfigArguments(
                    animation_file=self.__condition_mapping[icon],
                    width=9,
                    height=6,
                    frames=[],
                ),
                name=icon,
                refresh_interval=1000,
                module_type="animator",
            )
        )
        self.__icon_module_thread = Thread(
            target=self.__icon_module.start,
            args=(update_device, write_queue),
            name=f"weather_{icon}_{id(self)}_{id(self.__icon_module)}",
        )
        self.__icon_module_thread.start()
