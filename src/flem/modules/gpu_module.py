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


class GpuModule(MatrixModule):
    __line_module: LineModule = None
    __config: GpuConfig = None
    __previous_value: str = "NA"

    running = True
    module_name = "GPU Module"

    def __init__(self, config: GpuConfig = None, width: int = 3, height: int = 18):
        super().__init__(config, width, height)

        # pylint: disable=W0238
        self.width = width
        self.height = height
        # pylint: enable=W0238

        if not isinstance(config, GpuConfig):
            self.__config = GpuConfigSchema().load(ModuleSchema().dump(config))
        else:
            self.__config = config

        line_config = LineConfig(
            name="line",
            position=ModulePositionConfig(x=config.position.x, y=config.position.y + 5),
            refresh_interval=config.refresh_interval,
            module_type="line",
            arguments=LineConfigArguments(line_style="solid", width=width),
        )
        self.__line_module = LineModule(line_config, self.width)

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
        """
        Resets the GPU module to its initial state.
        """
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
        """
        Writes the GPU usage to the matrix display and executes the callback if specified.
        """
        try:
            self._write_object(
                "g", write_queue, self.__config.position.y, self.__config.position.x
            )

            self.__line_module.write(update_device, write_queue, False)

            while self.running:
                raw = subprocess.check_output(
                    [self.__config.arguments.gpu_command]
                    + self.__config.arguments.gpu_command_arguments.split(",")
                ).decode()
                raw = re.sub(r'"(\s*\n\s+")', r'",\1', raw)
                gpu_info = json.loads(raw)
                gpu_percentage = gpu_info[self.__config.arguments.gpu_index][
                    self.__config.arguments.gpu_util_property
                ][:-1]

                gpu_cols = len(gpu_percentage)

                if gpu_cols == 1:
                    gpu_percentage = "0" + gpu_percentage

                start_row = self.__config.position.y + 7

                if gpu_percentage == "100":
                    self._write_object(
                        "!", write_queue, start_row, self.__config.position.x
                    )
                else:
                    for i, char in enumerate(gpu_percentage):
                        if char == self.__previous_value[i]:
                            start_row += 6
                            continue

                        self._write_object(
                            char,
                            write_queue,
                            start_row,
                            self.__config.position.x,
                        )
                        start_row += 6

                if self.__previous_value == "100":
                    for i in range(3):
                        write_queue(
                            (
                                self.__config.position.x + i,
                                self.__config.position.y + 12,
                                False,
                            )
                        )

                self.__previous_value = gpu_percentage
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

    def _exclamation(
        self,
        write_queue: Callable[[tuple[int, int, bool]], None],
        start_row: int,
        start_col: int,
    ) -> None:
        # fmt: off
        char_arr = [
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
            [1, 1, 1],
        ]
        # fmt: on

        self._write_array(char_arr, start_row, start_col, write_queue)
