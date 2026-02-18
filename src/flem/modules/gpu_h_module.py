# pylint: disable=abstract-method, missing-module-docstring

import json
import re
import subprocess
from typing import Callable

from loguru import logger

from flem.models.config_schema import ModuleSchema
from flem.models.modules.gpu_config import GpuConfig, GpuConfigSchema
from flem.models.modules.line_config import LineConfig, LineConfigArguments
from flem.modules.matrix_module import MatrixModule
from flem.modules.line_module import LineModule
from flem.models.config import ModulePositionConfig


class GpuHModule(MatrixModule):
    __line_module: LineModule = None
    __temperature_line_module: LineModule = None
    __width = 9
    __height = 12
    __config: GpuConfig = None
    __previous_value: str = "NA"
    __previous_temp: str = "NA"
    __max_gpu_percentage = 100

    # I might parameterize this, but 100 seems like a reasonable max
    __max_temperature = 100

    running = True
    module_name = "GPU Module"

    def __init__(self, config: GpuConfig = None, width: int = 9, height: int = 12):
        super().__init__(config, width, height)

        if not isinstance(config, GpuConfig):
            self.__config = GpuConfigSchema().load(ModuleSchema().dump(config))
        else:
            self.__config = config

        self.width = width
        line_config = LineConfig(
            name="line",
            position=ModulePositionConfig(x=config.position.x, y=config.position.y + 5),
            refresh_interval=config.refresh_interval,
            module_type="line",
            arguments=LineConfigArguments(line_style="solid", width=width),
        )
        self.__line_module = LineModule(line_config, self.width)

        if self.__config.arguments.show_temp:
            # self.__height = self.__height + 7
            temperature_line_config = LineConfig(
                name="temperature_line",
                position=ModulePositionConfig(
                    x=config.position.x,
                    y=config.position.y
                    + (10 if self.__config.arguments.use_bar_graph else 13),
                ),
                refresh_interval=config.refresh_interval,
                module_type="line",
                arguments=LineConfigArguments(line_style="dashed", width=width),
            )
            self.__temperature_line_module = LineModule(
                temperature_line_config, self.width
            )

    def start(
        self,
        update_device: Callable[[], None],
        write_queue: Callable[[tuple[int, int, bool]], None],
        execute_callback: bool = True,
    ):
        self.running = True
        self.reset()
        self.write(update_device, write_queue, execute_callback)

    def stop(self) -> None:
        self.running = False
        return super().stop()

    def reset(self):
        self.__previous_temp = "NA"
        self.__previous_value = "NA"
        return super().reset()

    def write(
        self,
        update_device: Callable[[], None],
        write_queue: Callable[[tuple[int, int, bool]], None],
        execute_callback: bool = True,
        refresh_override: int = None,
        running: bool = True,
    ) -> None:
        try:
            self._write_object(
                "g", write_queue, self.__config.position.y, self.__config.position.x
            )
            self._write_object(
                "p", write_queue, self.__config.position.y, self.__config.position.x + 3
            )
            self._write_object(
                "u", write_queue, self.__config.position.y, self.__config.position.x + 6
            )

            self.__line_module.write(update_device, write_queue, False)

            if self.__config.arguments.show_temp:
                self.__temperature_line_module.write(update_device, write_queue, False)

            while self.running:

                raw = subprocess.check_output(
                    [self.__config.arguments.gpu_command]
                    + self.__config.arguments.gpu_command_arguments
                ).decode()
                raw = re.sub(r'"(\s*\n\s+")', r'",\1', raw)
                gpu_info = json.loads(raw)

                gpu_percentage = gpu_info[self.__config.arguments.gpu_index][
                    self.__config.arguments.gpu_util_property
                ][:-1]

                if self.__config.arguments.use_bar_graph:
                    self._write_gpu_pips(gpu_percentage, write_queue)
                else:
                    self._write_gpu_value(gpu_percentage, write_queue)

                if self.__config.arguments.show_temp:
                    temperature = gpu_info[self.__config.arguments.gpu_index][
                        self.__config.arguments.gpu_temp_property
                    ][:-1]
                    if self.__config.arguments.use_bar_graph:
                        self._write_temperature_pips(temperature, write_queue)
                    else:
                        self._write_gpu_temp(temperature, write_queue)

                super().write(
                    update_device,
                    write_queue,
                    execute_callback,
                    refresh_override,
                    self.running,
                )
        except (IndexError, ValueError, TypeError) as e:
            logger.exception(f"Error while running {self.module_name}: {e}")
            super().stop()
            super().clear_module(update_device, write_queue)

    def _write_gpu_value(
        self, gpu_percentage: str, write_queue: Callable[[tuple[int, int, bool]], None]
    ) -> None:
        gpu_cols = len(gpu_percentage)

        if gpu_cols == 1:
            gpu_percentage = "0" + gpu_percentage

        start_row = self.__config.position.y + 7
        start_col = self.__config.position.x + 1

        if gpu_percentage == "100":
            self._write_object("!", write_queue, start_row, start_col)
        else:
            for i, char in enumerate(gpu_percentage):
                if char == self.__previous_value[i]:
                    start_col += 4
                    continue

                self._write_object(
                    char,
                    write_queue,
                    start_row,
                    start_col,
                )
                start_col += 4

    def _write_gpu_temp(
        self, temperature: str, write_queue: Callable[[tuple[int, int, bool]], None]
    ) -> None:
        start_row = self.__config.position.y + 15
        start_col = self.__config.position.x + 1
        for i, char in enumerate(temperature):
            if char == self.__previous_temp[i]:
                start_col += 4
                continue

            self._write_object(
                char,
                write_queue,
                start_row,
                start_col,
            )
            start_col += 4

        self.__previous_temp = temperature

    def _write_temperature_pips(
        self,
        gpu_temperature: str,
        write_queue: Callable[[tuple[int, int, bool]], None],
    ):
        start_row = self.__config.position.y + 12
        num_pips = super()._calculate_pips_to_show(
            int(gpu_temperature), self.__max_temperature, 18
        )

        col = 0
        for i in range(18):
            pip_on = i < num_pips
            if i % 2 == 0:
                write_queue((col, start_row, pip_on))
            else:
                write_queue((col, start_row + 1, pip_on))
                col += 1

    def _write_gpu_pips(
        self,
        gpu_percentage: str,
        write_queue: Callable[[tuple[int, int, bool]], None],
    ):
        start_row = self.__config.position.y + 7
        num_pips = super()._calculate_pips_to_show(
            int(gpu_percentage), self.__max_gpu_percentage, 18
        )

        col = 0
        for i in range(18):
            pip_on = i < num_pips
            if i % 2 == 0:
                write_queue((col, start_row, pip_on))
            else:
                write_queue((col, start_row + 1, pip_on))
                col += 1

    def _g(
        self,
        write_queue: Callable[[tuple[int, int, bool]], None],
        start_row: int,
        start_col: int,
    ) -> None:
        # fmt: off
        char_arr = [
            [1, 1, 0],
            [1, 0, 0],
            [1, 0, 1],
            [1, 1, 1],
        ]
        # fmt: on

        self._write_array(char_arr, start_row, start_col, write_queue)

    def _exclamation(
        self, write_queue: callable, start_row: int, start_col: int
    ) -> None:
        # fmt: off
        char_arr = [
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
        ]
        # fmt: on

        self._write_array(char_arr, start_row, start_col, write_queue)
