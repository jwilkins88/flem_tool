# pylint: disable=abstract-method, missing-module-docstring
from time import sleep
from typing import Callable
import traceback
import sys

import psutil

from modules.matrix_module import MatrixModule
from models import ModuleConfig


class RamModule(MatrixModule):
    __previous_value = ["NA", 0]
    __config: ModuleConfig = None

    module_name = "RAM Module"

    def __init__(self, config: ModuleConfig, width: int = 9, height: int = 11):
        self.__config = config
        super().__init__(config, width, height)

    def reset(self):
        self.__previous_value = ["NA", 0]
        return super().reset()

    def write(
        self,
        update_device: Callable[[], None],
        write_queue: Callable[[tuple[int, int, bool]], None],
        execute_callback: bool = True,
    ) -> None:
        try:
            self._write_text(
                "g",
                write_queue,
                self.__config.position.y + 7,
                self.__config.position.x + 2,
            )
            self._write_text(
                "b",
                write_queue,
                self.__config.position.y + 7,
                self.__config.position.x + 6,
            )
            while self.running:
                used_memory = str(
                    round(psutil.virtual_memory().used / 1000 / 1000 / 1000, 2)
                ).split(".")
                start_col = 0
                start_row = self.__config.position.y
                if len(used_memory[0]) == 1:
                    used_memory[0] = "0" + used_memory[0]

                for i, char in enumerate(used_memory[0]):
                    if char == self.__previous_value[0][i]:
                        start_col += 4
                        continue
                    self._write_number(char, write_queue, start_row, start_col)
                    start_col += 4

                used_memory[1] = int(used_memory[1])
                self.write_fraction(
                    used_memory[1], 0, write_queue, 8, self.__config.position.y
                )
                self.write_fraction(
                    used_memory[1], 10, write_queue, 8, self.__config.position.y + 1
                )
                self.write_fraction(
                    used_memory[1], 20, write_queue, 8, self.__config.position.y + 2
                )
                self.write_fraction(
                    used_memory[1], 30, write_queue, 8, self.__config.position.y + 3
                )
                self.write_fraction(
                    used_memory[1], 40, write_queue, 8, self.__config.position.y + 4
                )
                self.write_fraction(
                    used_memory[1], 50, write_queue, 0, self.__config.position.y + 6
                )
                self.write_fraction(
                    used_memory[1], 60, write_queue, 0, self.__config.position.y + 7
                )
                self.write_fraction(
                    used_memory[1], 70, write_queue, 0, self.__config.position.y + 8
                )
                self.write_fraction(
                    used_memory[1], 80, write_queue, 0, self.__config.position.y + 9
                )
                self.write_fraction(
                    used_memory[1], 90, write_queue, 0, self.__config.position.y + 10
                )

                self.__previous_value = used_memory
                super().write(update_device, write_queue, execute_callback)
                sleep(self.__config.refresh_interval / 1000)
        except (IndexError, ValueError, TypeError) as e:
            print(f"Error while running {self.module_name}: {e}")
            traceback.print_exc(*sys.exc_info())
            super().stop()
            super().clear_module(update_device, write_queue)

    def write_fraction(
        self,
        fraction_value: int,
        comparison_value: int,
        write_queue: Callable[[tuple[int, int, bool]], None],
        start_col: int,
        start_row: int,
    ) -> None:
        if fraction_value > comparison_value:
            write_queue(
                (
                    start_col,
                    start_row,
                    True,
                )
            )
        else:
            write_queue(
                (
                    start_col,
                    start_row,
                    False,
                )
            )
