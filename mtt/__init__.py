import os

from threading import RLock
from path import Path

import mtt.config as base_config

__all__ = ['config', 'lock']


class ConfigAccessor:
    def __init__(self, configuration_items):
        self.config = configuration_items

    def update(self, other):
        self.config.update(other.config if 'config' in other else other)

    def __getattr__(self, item):
        if item in self.config:
            return self.config[item]

        raise AttributeError(f'Unknown configuration option \'{item}\'')

    def __getitem__(self, item):
        try:
            return self.config[item]
        except KeyError:
            raise KeyError(f'Unknown configuration option \'{item}\'')


def get_variables_in_module(module_name: str) -> ConfigAccessor:
    module = globals().get(module_name, None)
    module_type = type(os)
    class_type = type(Path)

    variables = {}
    if module:
        variables = {key: value for key, value in module.__dict__.items()
                     if not (key.startswith('__') or key.startswith('_'))
                     and not isinstance(value, module_type)
                     and not isinstance(value, class_type)}
    return ConfigAccessor(variables)


config = get_variables_in_module('base_config')

try:
    import mtt.user_config as user_config
    config.update(get_variables_in_module('user_config'))
except ImportError:
    pass

lock = RLock()
