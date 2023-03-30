import pytest
from click.testing import CliRunner
from loto import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.parametrize(
    "file_args",
    (
        (['-r', 'loto_data/loto']),
        (['-r', 'loto_data/euromillion']),
        (['-f', 'loto_data/euromillions_201902.csv', '-f', 'loto_201902.csv']),
        (['-r', 'loto_data/loto']),
    )
)
@pytest.mark.parametrize(
    "format_args",
    (
        ['-l', '5_boules'],
        ['-l', '6_boules'],
        ['-l', 'euromillion'],
        [],
    )
)
@pytest.mark.parametrize(
    "other_args",
    (
        ['-e', '1-1-1-1-1+1'],
        ['-e', '1-1-1-1-1:1'],
        [],
    )
)
def test_gen(runner: CliRunner, file_args: list[str], format_args: list[str], other_args: list[str]):
    runner.invoke(main, [*file_args, *format_args, *other_args])
