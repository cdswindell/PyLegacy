import argparse

from src.cli.switch import SwitchCli


class TrainControl:
    def __init__(self, arg_parser: argparse.ArgumentParser) -> None:
        pass
        self.run()

    def run(self) -> None:
        while True:
            try:
                ui: str = input(">> ")
                self._handle_command(ui)
            except SystemExit as e:
                pass
            except argparse.ArgumentError:
                pass
            except KeyboardInterrupt:
                break

    def _handle_command(self, ui: str) -> None:
        if ui is None:
            return
        ui = ui.lower().strip()
        if ui:
            ui_parts = ui.split()
            ui_parser = SwitchCli.switch_parser()
            SwitchCli(ui_parser, ui_parts[1:])


if __name__ == '__main__':
    parser = argparse.ArgumentParser("Train Controls")
    TrainControl(parser)
