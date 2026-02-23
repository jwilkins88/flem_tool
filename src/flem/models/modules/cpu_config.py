# pylint: disable=missing-module-docstring, missing-class-docstring, unused-argument

from marshmallow import Schema, fields, post_load

from flem.models.config import ModuleConfig, ModulePositionConfig
from flem.models.config_schema import ModulePositionSchema, ModuleSchema


class CpuConfigArguments:
    def __init__(
        self,
        temp_sensor: str = None,
        temp_sensor_index: int = None,
        show_temp: bool = False,
        use_bar_graph: bool = False,
    ):
        self.show_temp = show_temp
        self.temp_sensor = temp_sensor
        self.temp_sensor_index = temp_sensor_index
        self.use_bar_graph = use_bar_graph


class CpuConfig(ModuleConfig):
    def __init__(
        self,
        name: str,
        module_type: str,
        position: ModulePositionConfig,
        refresh_interval: int,
        arguments: CpuConfigArguments,
    ):
        super().__init__(name, module_type, position, refresh_interval, arguments)
        self.arguments = arguments


class CpuConfigArgumentsSchema(Schema):
    temp_sensor = fields.Str(required=False, load_default=None)
    temp_sensor_index = fields.Int(required=False, load_default=None)
    show_temp = fields.Bool(required=False, load_default=False)
    use_bar_graph = fields.Bool(required=False, load_default=False)

    @post_load
    def make_module(self, data, **kwargs):
        """
        map to object
        """
        return CpuConfigArguments(**data)


class CpuConfigSchema(ModuleSchema):
    name = fields.Str()
    module_type = fields.Str()
    position = fields.Nested(ModulePositionSchema)
    refresh_interval = fields.Int()
    arguments = fields.Nested(CpuConfigArgumentsSchema)

    @post_load
    def make_module(self, data, **kwargs):
        """
        map to object
        """
        return CpuConfig(**data)
