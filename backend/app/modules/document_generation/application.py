from typing import Protocol


class TechnicalReportDocumentGenerator(Protocol):
    def generate(self, report: dict) -> bytes: ...


class GenerateTechnicalReport:
    def __init__(self, generator: TechnicalReportDocumentGenerator):
        self.generator = generator

    def execute(self, report: dict) -> bytes:
        return self.generator.generate(report)
