from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    def __init__(self, config):
        self.config = config
        self.results = {}

    @abstractmethod
    def calculate(self):
        pass

    @abstractmethod
    def display_results(self):
        pass